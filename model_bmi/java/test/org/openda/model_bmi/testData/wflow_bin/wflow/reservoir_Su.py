# -*- coding: utf-8 -*-
"""
Created on Thu Apr 03 16:31:35 2014

@author: TEuser

List all function versions
"""

import numpy
import pdb
from copy import copy as copylist

try:
    from  wflow.wf_DynamicFramework import *
except ImportError:
    from  wf_DynamicFramework import *
import scipy
import JarvisCoefficients

def selectSuR(i):
    """
    not all functions are still in this file, the older functions can be found
    (with the same numbering) in h:\My Documents\memo's\python scripts\wflow\
    """
    if i == 1:
        name = 'unsatZone_LP_beta'
    elif i == 2:
        name = 'unsatZone_LP'
    elif i == 3:
        name = 'unsatZone_SF'
    elif i == 4:
        name = 'unsatZone_EisEp'
    elif i == 5:
        name = 'unsatZone_drain'
    elif i == 6:
        name = 'unsatZone_drain_split'
    elif i == 7:
        name = 'unsatZone_drain_Sumin'
    elif i == 8:
        name = 'unsatZone_drain_DZ'
    elif i == 9:
        name = 'unsatZone_drain_split_DZ'
    elif i == 10:
        name = 'unsatZone_withAgri'
    elif i == 11:
        name = 'unsatZone_withAgri_oldBeta'
    elif i == 12:
        name = 'unsatZone_LP_beta_Jarvis'
    elif i == 13:
        name = 'unsatZone_LP_beta_Ep'
    elif i == 14:
        name = 'unsatZone_withAgri_Ep'
    elif i == 15:
        name = 'unsatZone_withAgri_Jarvis'
    elif i == 16:
        name = 'unsatZone_forAgri_Jarvis'
    elif i == 17:
        name = 'unsatZone_forAgri_Ep'
    elif i == 18:
        name = 'unsatZone_forAgri_Jarvis_cropG'
    elif i == 19:
        name = 'unsatZone_forAgri_Ep_cropG'
    elif i == 20:
        name = 'unsatZone_LP_beta_Ep_cropG'
    return name

def unsatZone_no_reservoir(self, k):
    """
    This function is used when no unsaturated zone reservoir is used and only
    passes fluxes from the upper reservoirs to the lower
    Qu = Pe
    Eu = 0.
    Perc = 0.
    Cap = 0.
    Storage in unsaturated zone = 0.
    """
    self.Qu_[k] = max(self.Pe_[k], 0)
    self.Eu_[k] = 0.
    self.Perc_[k] = 0.
    self.Su_[k] = 0.
    self.Cap_[k] = 0.
    self.wbSu_[k] = self.Pe - self.Eu - self.Qu - self.Perc + self.Cap - self.Su[k] + self.Su_t[k]

def unsatZone_LP_beta(self,k):
    """
    - Potential evaporation is decreased by energy used for interception evaporation
    - Formula for evaporation linear until LP, from than with potential rate
    - Outgoing fluxes are determined based on (value in previous timestep + inflow)
    and if this leads to negative storage, the outgoing fluxes are corrected to rato
    - Qu is determined with a beta function (same as in HBV?)
    - Code for ini-file: 1
    """
    self.Su[k] = ifthenelse(self.Su_t[k] + self.Pe > self.sumax[k], self.sumax[k], self.Su_t[k] + self.Pe)
    self.Quadd = ifthenelse(self.Su_t[k] + self.Pe > self.sumax[k], self.Su_t[k] + self.Pe - self.sumax[k], 0)
    self.SuN = self.Su[k] / self.sumax[k]
    self.SiN = self.Si[k] / self.imax[k]

    self.Eu1 = max((self.PotEvaporation - self.Ei),0) * min(self.Su[k] / (self.sumax[k] * self.LP[k]),1)

    self.Qu1 = (self.Pe - self.Quadd) * (1 - (1 - self.SuN) ** self.beta[k])
    self.Perc1 = self.perc[k] * self.SuN
    self.Su[k] = self.Su_t[k] + (self.Pe - self.Quadd) - self.Qu1 - self.Eu1 - self.Perc1

    self.Su_diff = ifthenelse(self.Su[k] < 0, self.Su[k], 0)
    self.Eu = self.Eu1 + (self.Eu1 / ifthenelse(self.Qu1 + self.Eu1 +self.Perc1 > 0 , self.Qu1 + self.Eu1 + self.Perc1 , 1)) * self.Su_diff
    self.Qu = self.Qu1 + (self.Qu1/ifthenelse(self.Qu1 + self.Eu1 + self.Perc1 > 0 , self.Qu1 + self.Eu1 + self.Perc1 , 1)) * self.Su_diff
    self.Perc = ifthenelse (self.Perc1 > 0, self.Perc1 + (self.Perc1/ifthenelse(self.Qu1 + self.Eu1 + self.Perc1 > 0 , self.Qu1 + self.Eu1 + self.Perc1 , 1)) * self.Su_diff, self.Perc1)
    self.Su[k] = self.Su_t[k] + (self.Pe - self.Quadd) - self.Eu - self.Qu - self.Perc
    self.Su[k] = ifthenelse(self.Su[k] < 0, 0 , self.Su[k])
    self.Su_diff2 = ifthen(self.Su[k] < 0, self.Su[k])

    self.Cap = min(self.cap[k] * (1 - self.Su[k] / self.sumax[k]), self.Ss)
    self.Su[k] = self.Su[k] + self.Cap

    self.wbSu_[k] = self.Pe - self.Eu - self.Qu - self.Quadd - self.Perc + self. Cap - self.Su[k] + self.Su_t[k]

    self.Eu_[k] = self.Eu
    self.Qu_[k] = self.Qu + self.Quadd
    self.Cap_[k] = self.Cap
    self.Perc_[k] = self.Perc
#    self.Su_diff_[k] = self.Su_diff
#    self.Quadd_[k] = self.Quadd


def unsatZone_LP_beta_Jarvis(self,k):
    """
    - Potential evaporation is decreased by energy used for interception evaporation
    - Formula for evaporation based on Jarvis stress functions
    - Outgoing fluxes are determined based on (value in previous timestep + inflow)
    and if this leads to negative storage, the outgoing fluxes are corrected to rato --> Eu is
    no longer taken into account for this correction
    - Qu is determined with a beta function (same as in HBV?)
    - Code for ini-file: 12
    """
    self.Su[k] = ifthenelse(self.Su_t[k] + self.Pe > self.sumax[k], self.sumax[k], self.Su_t[k] + self.Pe)
    self.Quadd = ifthenelse(self.Su_t[k] + self.Pe > self.sumax[k], self.Su_t[k] + self.Pe - self.sumax[k], 0)
    self.SuN = self.Su[k] / self.sumax[k]
    self.SiN = self.Si[k] / self.imax[k]

    JarvisCoefficients.calcEu(self,k,1)           #calculation of Eu based on Jarvis stress functions

    self.Qu1 = (self.Pe - self.Quadd) * (1 - (1 - self.SuN) ** self.beta[k])
    self.Perc1 = self.perc[k] * self.SuN
    self.Su[k] = self.Su_t[k] + (self.Pe - self.Quadd) - self.Qu1 - self.Eu - self.Perc1

    self.Su_diff = ifthenelse(self.Su[k] < 0, self.Su[k], 0)
    self.Qu = self.Qu1 + (self.Qu1/ifthenelse(self.Qu1 + self.Perc1 > 0 , self.Qu1 + self.Perc1 , 1)) * self.Su_diff
    self.Perc = ifthenelse (self.Perc1 > 0, self.Perc1 + (self.Perc1/ifthenelse(self.Qu1 + self.Perc1 > 0 , self.Qu1 + self.Perc1 , 1)) * self.Su_diff, self.Perc1)
    self.Su[k] = self.Su_t[k] + (self.Pe - self.Quadd) - self.Eu - self.Qu - self.Perc
    self.Su[k] = ifthenelse(self.Su[k] < 0, 0 , self.Su[k])
    self.Su_diff2 = ifthen(self.Su[k] < 0, self.Su[k])

    self.Cap = min(self.cap[k] * (1 - self.Su[k] / self.sumax[k]), self.Ss)
    self.Su[k] = self.Su[k] + self.Cap

    self.wbSu_[k] = self.Pe - self.Eu - self.Qu - self.Quadd - self.Perc + self. Cap - self.Su[k] + self.Su_t[k]

    self.Eu_[k] = self.Eu
    self.Qu_[k] = self.Qu + self.Quadd
    self.Cap_[k] = self.Cap
    self.Perc_[k] = self.Perc
#    self.Su_diff_[k] = self.Su_diff
#    self.Quadd_[k] = self.Quadd


def unsatZone_LP_beta_Ep(self,k):
    """
    - Potential evaporation is calculated with formula in 'JarvisCoefficients', but without
    using the Jarvis stress functions
    - Potential evaporation is decreased by energy used for interception evaporation
    - Formula for evaporation linear until LP, from than with potential rate
    - Outgoing fluxes are determined based on (value in previous timestep + inflow)
    and if this leads to negative storage, the outgoing fluxes are corrected to rato
    - Qu is determined with a beta function (same as in HBV?)
    - Code for ini-file: 13
    """

    JarvisCoefficients.calcEp(self,k)
    self.PotEvaporation = self.EpHour

    self.Su[k] = ifthenelse(self.Su_t[k] + self.Pe > self.sumax[k], self.sumax[k], self.Su_t[k] + self.Pe)
    self.Quadd = ifthenelse(self.Su_t[k] + self.Pe > self.sumax[k], self.Su_t[k] + self.Pe - self.sumax[k], 0)
    self.SuN = self.Su[k] / self.sumax[k]
    self.SiN = self.Si[k] / self.imax[k]

    self.Eu1 = max((self.PotEvaporation - self.Ei),0) * min(self.Su[k] / (self.sumax[k] * self.LP[k]),1)

    self.Qu1 = (self.Pe - self.Quadd) * (1 - (1 - self.SuN) ** self.beta[k])
    self.Perc1 = self.perc[k] * self.SuN
    self.Su[k] = self.Su_t[k] + (self.Pe - self.Quadd) - self.Qu1 - self.Eu1 - self.Perc1

    self.Su_diff = ifthenelse(self.Su[k] < 0, self.Su[k], 0)
    self.Eu = self.Eu1 + (self.Eu1 / ifthenelse(self.Qu1 + self.Eu1 +self.Perc1 > 0 , self.Qu1 + self.Eu1 + self.Perc1 , 1)) * self.Su_diff
    self.Qu = self.Qu1 + (self.Qu1/ifthenelse(self.Qu1 + self.Eu1 + self.Perc1 > 0 , self.Qu1 + self.Eu1 + self.Perc1 , 1)) * self.Su_diff
    self.Perc = ifthenelse (self.Perc1 > 0, self.Perc1 + (self.Perc1/ifthenelse(self.Qu1 + self.Eu1 + self.Perc1 > 0 , self.Qu1 + self.Eu1 + self.Perc1 , 1)) * self.Su_diff, self.Perc1)
    self.Su[k] = self.Su_t[k] + (self.Pe - self.Quadd) - self.Eu - self.Qu - self.Perc
    self.Su[k] = ifthenelse(self.Su[k] < 0, 0 , self.Su[k])
    self.Su_diff2 = ifthen(self.Su[k] < 0, self.Su[k])

    self.Cap = min(self.cap[k] * (1 - self.Su[k] / self.sumax[k]), self.Ss)
    self.Su[k] = self.Su[k] + self.Cap

    self.wbSu_[k] = self.Pe - self.Eu - self.Qu - self.Quadd - self.Perc + self. Cap - self.Su[k] + self.Su_t[k]

    self.Eu_[k] = self.Eu
    self.Qu_[k] = self.Qu + self.Quadd
    self.Cap_[k] = self.Cap
    self.Perc_[k] = self.Perc
#    self.Su_diff_[k] = self.Su_diff
#    self.Quadd_[k] = self.Quadd

def unsatZone_LP_beta_Ep_cropG(self,k):
    """
    - Potential evaporation is calculated with formula in 'JarvisCoefficients', but without
    using the Jarvis stress functions
    - Potential evaporation is decreased by energy used for interception evaporation
    - Formula for evaporation linear until LP, from than with potential rate
    - Outgoing fluxes are determined based on (value in previous timestep + inflow)
    and if this leads to negative storage, the outgoing fluxes are corrected to rato
    - Qu is determined with a beta function (same as in HBV?)
    - root zone storage for crop land is decreased in autumn and winter
    - Code for ini-file: 20
    """

    JarvisCoefficients.calcEp(self,k)
    self.PotEvaporation = self.EpHour
#
#    pdb.set_trace()
    self.cropG_scal = pcr2numpy(self.cropG,NaN)
    if any(self.cropG_scal == 1):
        self.sumax2 = self.sumax[k]
    elif any(self.cropG_scal > 0):
#        pdb.set_trace()
        self.sumax2 = self.sumax[k] * (1 - numpy.max(self.cropG_scal[self.cropG_scal >= 0]) * (1-self.redsu[k]))
    else:
        self.sumax2 = self.sumax[k] * self.redsu[k]

    self.Su[k] = ifthenelse(self.Su_t[k] + self.Pe > self.sumax2, self.sumax2, self.Su_t[k] + self.Pe)
    self.Quadd = ifthenelse(self.Su_t[k] + self.Pe > self.sumax2, self.Su_t[k] + self.Pe - self.sumax2, 0)
    self.SuN = self.Su[k] / self.sumax2
    self.SiN = self.Si[k] / self.imax[k]

    self.Eu1 = max((self.PotEvaporation - self.Ei),0) * min(self.Su[k] / (self.sumax2 * self.LP[k]),1)

    self.Qu1 = (self.Pe - self.Quadd) * (1 - (1 - self.SuN) ** self.beta[k])
    self.Perc1 = self.perc[k] * self.SuN
    self.Su[k] = self.Su_t[k] + (self.Pe - self.Quadd) - self.Qu1 - self.Eu1 - self.Perc1

    self.Su_diff = ifthenelse(self.Su[k] < 0, self.Su[k], 0)
    self.Eu = self.Eu1 + (self.Eu1 / ifthenelse(self.Qu1 + self.Eu1 +self.Perc1 > 0 , self.Qu1 + self.Eu1 + self.Perc1 , 1)) * self.Su_diff
    self.Qu = self.Qu1 + (self.Qu1/ifthenelse(self.Qu1 + self.Eu1 + self.Perc1 > 0 , self.Qu1 + self.Eu1 + self.Perc1 , 1)) * self.Su_diff
    self.Perc = ifthenelse (self.Perc1 > 0, self.Perc1 + (self.Perc1/ifthenelse(self.Qu1 + self.Eu1 + self.Perc1 > 0 , self.Qu1 + self.Eu1 + self.Perc1 , 1)) * self.Su_diff, self.Perc1)
    self.Su[k] = self.Su_t[k] + (self.Pe - self.Quadd) - self.Eu - self.Qu - self.Perc
    self.Su[k] = ifthenelse(self.Su[k] < 0, 0 , self.Su[k])
    self.Su_diff2 = ifthen(self.Su[k] < 0, self.Su[k])

    self.Cap = min(self.cap[k] * (1 - self.Su[k] / self.sumax2), self.Ss)
    self.Su[k] = self.Su[k] + self.Cap

    self.wbSu_[k] = self.Pe - self.Eu - self.Qu - self.Quadd - self.Perc + self. Cap - self.Su[k] + self.Su_t[k]

    self.Eu_[k] = self.Eu
    self.Qu_[k] = self.Qu + self.Quadd
    self.Cap_[k] = self.Cap
    self.Perc_[k] = self.Perc
#    self.Su_diff_[k] = self.Su_diff
#    self.Quadd_[k] = self.Quadd

def unsatZone_forAgri_Jarvis(self,k):
    """
    - Potential evaporation is decreased by energy used for interception evaporation
    - Formula for evaporation based on Jarvis stress functions
    - Outgoing fluxes are determined based on (value in previous timestep + inflow)
    and if this leads to negative storage, the outgoing fluxes are corrected to rato --> Eu is
    no longer taken into account for this correction
    - Qu is determined with a beta function (same as in HBV?)
    - inflow is infiltration from agriculture reservoir
    - Code for ini-file: 16
    """
    self.Su[k] = ifthenelse(self.Su_t[k] + self.Fa > self.sumax[k], self.sumax[k], self.Su_t[k] + self.Fa)
    self.Quadd = ifthenelse(self.Su_t[k] + self.Fa > self.sumax[k], self.Su_t[k] + self.Fa - self.sumax[k], 0)
    self.SuN = self.Su[k] / self.sumax[k]
    self.SiN = self.Si[k] / self.imax[k]

    JarvisCoefficients.calcEu(self,k,2)           #calculation of Eu based on Jarvis stress functions
    self.Eu1 = self.Eu

    self.Qu1 = (self.Fa - self.Quadd) * (1 - (1 - self.SuN) ** self.beta[k])
    self.Perc1 = self.perc[k] * self.SuN
    self.Su[k] = self.Su_t[k] + (self.Fa - self.Quadd) - self.Qu1 - self.Eu - self.Perc1

    self.Su_diff = ifthenelse(self.Su[k] < 0, self.Su[k], 0)
    self.Eu = self.Eu1 + (self.Eu1 / ifthenelse(self.Qu1 + self.Eu1 + self.Perc1 > 0 , self.Qu1 + self.Eu1 + self.Perc1 , 1)) * self.Su_diff
    self.Qu = self.Qu1 + (self.Qu1 / ifthenelse(self.Qu1 + self.Eu1 + self.Perc1 > 0 , self.Qu1 + self.Eu1 + self.Perc1 , 1)) * self.Su_diff
    self.Perc = ifthenelse (self.Perc1 > 0, self.Perc1 + (self.Perc1 / ifthenelse(self.Qu1 + self.Eu1 + self.Perc1 > 0 , self.Qu1 + self.Eu1 + self.Perc1 , 1)) * self.Su_diff, self.Perc1)
    self.Su[k] = self.Su_t[k] + (self.Fa - self.Quadd) - self.Eu - self.Qu - self.Perc
    self.Su[k] = ifthenelse(self.Su[k] < 0, 0 , self.Su[k])
    self.Su_diff2 = ifthen(self.Su[k] < 0, self.Su[k])

    self.Cap = min(self.cap[k] * (1 - self.Su[k] / self.sumax[k]), self.Ss)
    self.Su[k] = self.Su[k] + self.Cap

    self.wbSu_[k] = self.Fa - self.Eu - self.Qu - self.Quadd - self.Perc + self. Cap - self.Su[k] + self.Su_t[k]

    self.Eu_[k] = self.Eu
    self.Qu_[k] = self.Qu + self.Quadd
    self.Cap_[k] = self.Cap
    self.Perc_[k] = self.Perc

def unsatZone_forAgri_Ep(self,k):
    """
    - Potential evaporation is decreased by energy used for interception evaporation
    - Formula for evaporation based on beta/LP
    - Outgoing fluxes are determined based on (value in previous timestep + inflow)
    and if this leads to negative storage, the outgoing fluxes are corrected to rato --> Eu is
    no longer taken into account for this correction
    - Qu is determined with a beta function (same as in HBV?)
    - inflow is infiltration from agriculture reservoir
    - Code for ini-file: 17
    """

    JarvisCoefficients.calcEp(self,k)
    self.PotEvaporation = self.EpHour

    self.Su[k] = ifthenelse(self.Su_t[k] + self.Fa > self.sumax[k], self.sumax[k], self.Su_t[k] + self.Fa)
    self.Quadd = ifthenelse(self.Su_t[k] + self.Fa > self.sumax[k], self.Su_t[k] + self.Fa - self.sumax[k], 0)
    self.SuN = self.Su[k] / self.sumax[k]
    self.SiN = self.Si[k] / self.imax[k]

    self.Eu1 = max((self.PotEvaporation - self.Ei - self.Ea),0) * min(self.Su[k] / (self.sumax[k] * self.LP[k]),1)

    self.Qu1 = (self.Fa - self.Quadd) * (1 - (1 - self.SuN) ** self.beta[k])
    self.Perc1 = self.perc[k] * self.SuN
    self.Su[k] = self.Su_t[k] + (self.Fa - self.Quadd) - self.Qu1 - self.Eu - self.Perc1

    self.Su_diff = ifthenelse(self.Su[k] < 0, self.Su[k], 0)
    self.Eu = self.Eu1 + (self.Eu1 / ifthenelse(self.Qu1 + self.Eu1 + self.Perc1 > 0 , self.Qu1 + self.Eu1 + self.Perc1 , 1)) * self.Su_diff
    self.Qu = self.Qu1 + (self.Qu1 / ifthenelse(self.Qu1 + self.Eu1 + self.Perc1 > 0 , self.Qu1 + self.Eu1 + self.Perc1 , 1)) * self.Su_diff
    self.Perc = ifthenelse (self.Perc1 > 0, self.Perc1 + (self.Perc1 / ifthenelse(self.Qu1 + self.Eu1 + self.Perc1 > 0 , self.Qu1 + self.Eu1 + self.Perc1 , 1)) * self.Su_diff, self.Perc1)
    self.Su[k] = self.Su_t[k] + (self.Fa - self.Quadd) - self.Eu - self.Qu - self.Perc
    self.Su[k] = ifthenelse(self.Su[k] < 0, 0 , self.Su[k])
    self.Su_diff2 = ifthen(self.Su[k] < 0, self.Su[k])

    self.Cap = min(self.cap[k] * (1 - self.Su[k] / self.sumax[k]), self.Ss)
    self.Su[k] = self.Su[k] + self.Cap

    self.wbSu_[k] = self.Fa - self.Eu - self.Qu - self.Quadd - self.Perc + self. Cap - self.Su[k] + self.Su_t[k]

    self.Eu_[k] = self.Eu
    self.Qu_[k] = self.Qu + self.Quadd
    self.Cap_[k] = self.Cap
    self.Perc_[k] = self.Perc

def unsatZone_forAgri_Jarvis_cropG(self,k):
    """
    - Potential evaporation is decreased by energy used for interception evaporation
    - Formula for evaporation based on Jarvis stress functions
    - Outgoing fluxes are determined based on (value in previous timestep + inflow)
    and if this leads to negative storage, the outgoing fluxes are corrected to rato --> Eu is
    no longer taken into account for this correction
    - Qu is determined with a beta function (same as in HBV?)
    - inflow is infiltration from agriculture reservoir
    - Code for ini-file: 18
    """
    self.cropG_scal = pcr2numpy(self.cropG,NaN)
    if any(self.cropG_scal == 1):
        self.sumax2 = self.sumax[k]
    else:
        self.sumax2 = self.sumax[k] * self.redsu[k]

    self.Su[k] = ifthenelse(self.Su_t[k] + self.Fa > self.sumax2, self.sumax2, self.Su_t[k] + self.Fa)
    self.Quadd = ifthenelse(self.Su_t[k] + self.Fa > self.sumax2, self.Su_t[k] + self.Fa - self.sumax2, 0)
    self.SuN = self.Su[k] / self.sumax2
    self.SiN = self.Si[k] / self.imax[k]

    JarvisCoefficients.calcEu(self,k,2)           #calculation of Eu based on Jarvis stress functions
    self.Eu1 = self.Eu

    self.Qu1 = (self.Fa - self.Quadd) * (1 - (1 - self.SuN) ** self.beta[k])
    self.Perc1 = self.perc[k] * self.SuN
    self.Su[k] = self.Su_t[k] + (self.Fa - self.Quadd) - self.Qu1 - self.Eu - self.Perc1

    self.Su_diff = ifthenelse(self.Su[k] < 0, self.Su[k], 0)
    self.Eu = self.Eu1 + (self.Eu1 / ifthenelse(self.Qu1 + self.Eu1 + self.Perc1 > 0 , self.Qu1 + self.Eu1 + self.Perc1 , 1)) * self.Su_diff
    self.Qu = self.Qu1 + (self.Qu1 / ifthenelse(self.Qu1 + self.Eu1 + self.Perc1 > 0 , self.Qu1 + self.Eu1 + self.Perc1 , 1)) * self.Su_diff
    self.Perc = ifthenelse (self.Perc1 > 0, self.Perc1 + (self.Perc1 / ifthenelse(self.Qu1 + self.Eu1 + self.Perc1 > 0 , self.Qu1 + self.Eu1 + self.Perc1 , 1)) * self.Su_diff, self.Perc1)
    self.Su[k] = self.Su_t[k] + (self.Fa - self.Quadd) - self.Eu - self.Qu - self.Perc
    self.Su[k] = ifthenelse(self.Su[k] < 0, 0 , self.Su[k])
    self.Su_diff2 = ifthen(self.Su[k] < 0, self.Su[k])

    self.Cap = min(self.cap[k] * (1 - self.Su[k] / self.sumax2), self.Ss)
    self.Su[k] = self.Su[k] + self.Cap

    self.wbSu_[k] = self.Fa - self.Eu - self.Qu - self.Quadd - self.Perc + self. Cap - self.Su[k] + self.Su_t[k]

    self.Eu_[k] = self.Eu
    self.Qu_[k] = self.Qu + self.Quadd
    self.Cap_[k] = self.Cap
    self.Perc_[k] = self.Perc

def unsatZone_forAgri_Ep_cropG(self,k):
    """
    - Potential evaporation is decreased by energy used for interception evaporation
    - Formula for evaporation based on beta/LP
    - Outgoing fluxes are determined based on (value in previous timestep + inflow)
    and if this leads to negative storage, the outgoing fluxes are corrected to rato --> Eu is
    no longer taken into account for this correction
    - Qu is determined with a beta function (same as in HBV?)
    - inflow is infiltration from agriculture reservoir
    - Code for ini-file: 19
    """

    JarvisCoefficients.calcEp(self,k)
    self.PotEvaporation = self.EpHour

    self.cropG_scal = pcr2numpy(self.cropG,NaN)
    if any(self.cropG_scal == 1):
        self.sumax2 = self.sumax[k]
    else:
        self.sumax2 = self.sumax[k] * self.redsu[k]

    self.Su[k] = ifthenelse(self.Su_t[k] + self.Fa > self.sumax2, self.sumax2, self.Su_t[k] + self.Fa)
    self.Quadd = ifthenelse(self.Su_t[k] + self.Fa > self.sumax2, self.Su_t[k] + self.Fa - self.sumax2, 0)
    self.SuN = self.Su[k] / self.sumax2
    self.SiN = self.Si[k] / self.imax[k]

    self.Eu1 = max((self.PotEvaporation - self.Ei),0) * min(self.Su[k] / (self.sumax2 * self.LP[k]),1)

    self.Qu1 = (self.Fa - self.Quadd) * (1 - (1 - self.SuN) ** self.beta[k])
    self.Perc1 = self.perc[k] * self.SuN
    self.Su[k] = self.Su_t[k] + (self.Fa - self.Quadd) - self.Qu1 - self.Eu - self.Perc1

    self.Su_diff = ifthenelse(self.Su[k] < 0, self.Su[k], 0)
    self.Eu = self.Eu1 + (self.Eu1 / ifthenelse(self.Qu1 + self.Eu1 + self.Perc1 > 0 , self.Qu1 + self.Eu1 + self.Perc1 , 1)) * self.Su_diff
    self.Qu = self.Qu1 + (self.Qu1 / ifthenelse(self.Qu1 + self.Eu1 + self.Perc1 > 0 , self.Qu1 + self.Eu1 + self.Perc1 , 1)) * self.Su_diff
    self.Perc = ifthenelse (self.Perc1 > 0, self.Perc1 + (self.Perc1 / ifthenelse(self.Qu1 + self.Eu1 + self.Perc1 > 0 , self.Qu1 + self.Eu1 + self.Perc1 , 1)) * self.Su_diff, self.Perc1)
    self.Su[k] = self.Su_t[k] + (self.Fa - self.Quadd) - self.Eu - self.Qu - self.Perc
    self.Su[k] = ifthenelse(self.Su[k] < 0, 0 , self.Su[k])
    self.Su_diff2 = ifthen(self.Su[k] < 0, self.Su[k])

    self.Cap = min(self.cap[k] * (1 - self.Su[k] / self.sumax2), self.Ss)
    self.Su[k] = self.Su[k] + self.Cap

    self.wbSu_[k] = self.Fa - self.Eu - self.Qu - self.Quadd - self.Perc + self. Cap - self.Su[k] + self.Su_t[k]

    self.Eu_[k] = self.Eu
    self.Qu_[k] = self.Qu + self.Quadd
    self.Cap_[k] = self.Cap
    self.Perc_[k] = self.Perc

def unsatZone_withAgri(self,k):
    """
    - Potential evaporation is decreased by energy used for interception evaporation
    - Formula for evaporation linear until LP, from than with potential rate
    - Outgoing fluxes are determined based on (value in previous timestep + inflow)
    and if this leads to negative storage, the outgoing fluxes are corrected to rato
    - Qu is determined with a beta function (same as in HBV?)
    - Code for ini-file: 10
    """
    self.Sa[k] = ifthenelse(self.Sa_t[k] + self.Pe > self.samax[k], self.samax[k], self.Sa_t[k] + self.Pe)
    self.Qaadd = ifthenelse(self.Sa_t[k] + self.Pe > self.samax[k], self.Sa_t[k] + self.Pe - self.samax[k], 0)
    self.SaN = self.Sa[k] / self.samax[k]

    self.Ea1 = max((self.PotEvaporation - self.Ei),0) * min(self.Sa[k] / (self.samax[k] * self.LP[k]),1)
    self.Qa1 = (self.Pe - self.Qaadd) * (1 - (1 - self.SaN) ** self.beta[k])
    self.Fa1 = self.famax[k] * (self.sumax[k] - self.Su[k]) / self.sumax[k]

    self.Sa[k] = self.Sa_t[k] + (self.Pe - self.Qaadd) - self.Qa1 - self.Ea1 - self.Fa1

    self.Sa_diff = ifthenelse(self.Sa[k] < 0, self.Sa[k], 0)
    self.Ea = self.Ea1 + (self.Ea1 / ifthenelse(self.Qa1 + self.Ea1 +self.Fa1 > 0 , self.Qa1 + self.Ea1 + self.Fa1 , 1)) * self.Sa_diff
    self.Qa = self.Qa1 + (self.Qa1/ifthenelse(self.Qa1 + self.Ea1 + self.Fa1 > 0 , self.Qa1 + self.Ea1 + self.Fa1 , 1)) * self.Sa_diff
    self.Fa = ifthenelse (self.Fa1 > 0, self.Fa1 + (self.Fa1/ifthenelse(self.Qa1 + self.Ea1 + self.Fa1 > 0 , self.Qa1 + self.Ea1 + self.Fa1 , 1)) * self.Sa_diff, self.Fa1)
    self.Sa[k] = self.Sa_t[k] + (self.Pe - self.Qaadd) - self.Ea - self.Qa - self.Fa
    self.Sa[k] = ifthenelse(self.Sa[k] < 0, 0 , self.Sa[k])
    self.Sa_diff2 = ifthen(self.Sa[k] < 0, self.Sa[k])

    self.Capa = min(self.cap[k] * (1 - self.Sa[k] / self.samax[k]), self.Su[k])
    self.Sa[k] = self.Sa[k] + self.Capa

    self.Su[k] = self.Su_t[k] + self.Fa - self.Capa
    self.Perc = self.perc[k] * (self.Su[k] / self.sumax[k])
    self.Su[k] = self.Su[k] - self.Perc

    self.wbSa_[k] = self.Pe - self.Ea - self.Qa - self.Qaadd - self.Fa + self. Capa - self.Sa[k] + self.Sa_t[k]
    self.wbSu_[k] = self.Fa - self.Perc - self. Capa - self.Su[k] + self.Su_t[k]

    self.Eu_[k] = self.Ea
    self.Qu_[k] = self.Qa + self.Qaadd
    self.Fa_[k] = self.Fa
    self.Cap_[k] = self.Cap
    self.Perc_[k] = self.Perc
#    self.Su_diff_[k] = self.Su_diff
#    self.Quadd_[k] = self.Qaadd


def unsatZone_withAgri_Ep(self,k):
    """
    - Potential evaporation is calculated with formula in 'JarvisCoefficients', but without
    using the Jarvis stress functions
    - Potential evaporation is decreased by energy used for interception evaporation
    - Formula for evaporation linear until LP, from than with potential rate
    - Outgoing fluxes are determined based on (value in previous timestep + inflow)
    and if this leads to negative storage, the outgoing fluxes are corrected to rato
    - Qu is determined with a beta function (same as in HBV?)
    - Code for ini-file: 14
    """

    JarvisCoefficients.calcEp(self,k)
    self.PotEvaporation = self.EpHour

    self.Sa[k] = ifthenelse(self.Sa_t[k] + self.Pe > self.samax[k], self.samax[k], self.Sa_t[k] + self.Pe)
    self.Qaadd = ifthenelse(self.Sa_t[k] + self.Pe > self.samax[k], self.Sa_t[k] + self.Pe - self.samax[k], 0)
    self.SaN = self.Sa[k] / self.samax[k]

    self.Ea1 = max((self.PotEvaporation - self.Ei),0) * min(self.Sa[k] / (self.samax[k] * self.LP[k]),1)
    self.Qa1 = (self.Pe - self.Qaadd) * (1 - (1 - self.SaN) ** self.beta[k])
    self.Fa1 = self.famax[k] * (self.sumax[k] - self.Su[k]) / self.sumax[k]

    self.Sa[k] = self.Sa_t[k] + (self.Pe - self.Qaadd) - self.Qa1 - self.Ea1 - self.Fa1

    self.Sa_diff = ifthenelse(self.Sa[k] < 0, self.Sa[k], 0)
    self.Ea = self.Ea1 + (self.Ea1 / ifthenelse(self.Qa1 + self.Ea1 +self.Fa1 > 0 , self.Qa1 + self.Ea1 + self.Fa1 , 1)) * self.Sa_diff
    self.Qa = self.Qa1 + (self.Qa1/ifthenelse(self.Qa1 + self.Ea1 + self.Fa1 > 0 , self.Qa1 + self.Ea1 + self.Fa1 , 1)) * self.Sa_diff
    self.Fa = ifthenelse (self.Fa1 > 0, self.Fa1 + (self.Fa1/ifthenelse(self.Qa1 + self.Ea1 + self.Fa1 > 0 , self.Qa1 + self.Ea1 + self.Fa1 , 1)) * self.Sa_diff, self.Fa1)
    self.Sa[k] = self.Sa_t[k] + (self.Pe - self.Qaadd) - self.Ea - self.Qa - self.Fa
    self.Sa[k] = ifthenelse(self.Sa[k] < 0, 0 , self.Sa[k])
    self.Sa_diff2 = ifthen(self.Sa[k] < 0, self.Sa[k])

    self.Capa = min(self.cap[k] * (1 - self.Sa[k] / self.samax[k]), self.Su[k])
    self.Sa[k] = self.Sa[k] + self.Capa

    self.Su[k] = self.Su_t[k] + self.Fa - self.Capa
    self.Perc = self.perc[k] * (self.Su[k] / self.sumax[k])
    self.Su[k] = self.Su[k] - self.Perc

    self.wbSa_[k] = self.Pe - self.Ea - self.Qa - self.Qaadd - self.Fa + self. Capa - self.Sa[k] + self.Sa_t[k]
    self.wbSu_[k] = self.Fa - self.Perc - self. Capa - self.Su[k] + self.Su_t[k]

    self.Eu_[k] = self.Ea
    self.Qu_[k] = self.Qa + self.Qaadd
    self.Fa_[k] = self.Fa
    self.Cap_[k] = self.Cap
    self.Perc_[k] = self.Perc
#    self.Su_diff_[k] = self.Su_diff
#    self.Quadd_[k] = self.Qaadd

def unsatZone_withAgri_Jarvis(self,k):
    """
    - Potential evaporation is calculated with formula in 'JarvisCoefficients', but without
    using the Jarvis stress functions
    - Potential evaporation is decreased by energy used for interception evaporation
    - Formula for evaporation linear until LP, from than with potential rate
    - Outgoing fluxes are determined based on (value in previous timestep + inflow)
    and if this leads to negative storage, the outgoing fluxes are corrected to rato
    - Qu is determined with a beta function (same as in HBV?)
    - Code for ini-file: 15
    """

    self.Sa[k] = ifthenelse(self.Sa_t[k] + self.Pe > self.samax[k], self.samax[k], self.Sa_t[k] + self.Pe)
    self.Qaadd = ifthenelse(self.Sa_t[k] + self.Pe > self.samax[k], self.Sa_t[k] + self.Pe - self.samax[k], 0)
    self.SaN = self.Sa[k] / self.samax[k]

    JarvisCoefficients.calcEu(self,k,1)           #calculation of Eu based on Jarvis stress functions
    self.Ea = self.Eu

    self.Qa1 = (self.Pe - self.Qaadd) * (1 - (1 - self.SaN) ** self.beta[k])
    self.Fa1 = self.famax[k] * (self.sumax[k] - self.Su[k]) / self.sumax[k]

    self.Sa[k] = self.Sa_t[k] + (self.Pe - self.Qaadd) - self.Qa1 - self.Ea - self.Fa1

    self.Sa_diff = ifthenelse(self.Sa[k] < 0, self.Sa[k], 0)
    self.Qa = self.Qa1 + (self.Qa1/ifthenelse(self.Qa1 + self.Fa1 > 0 , self.Qa1 + self.Fa1 , 1)) * self.Sa_diff
    self.Fa = ifthenelse (self.Fa1 > 0, self.Fa1 + (self.Fa1/ifthenelse(self.Qa1 + self.Fa1 > 0 , self.Qa1 + self.Fa1 , 1)) * self.Sa_diff, self.Fa1)
    self.Sa[k] = self.Sa_t[k] + (self.Pe - self.Qaadd) - self.Ea - self.Qa - self.Fa
    self.Sa[k] = ifthenelse(self.Sa[k] < 0, 0 , self.Sa[k])
    self.Sa_diff2 = ifthen(self.Sa[k] < 0, self.Sa[k])

    self.Capa = min(self.cap[k] * (1 - self.Sa[k] / self.samax[k]), self.Su[k])
    self.Sa[k] = self.Sa[k] + self.Capa

    self.Su[k] = self.Su_t[k] + self.Fa - self.Capa
    self.Perc = self.perc[k] * (self.Su[k] / self.sumax[k])
    self.Su[k] = self.Su[k] - self.Perc

    self.wbSa_[k] = self.Pe - self.Ea - self.Qa - self.Qaadd - self.Fa + self. Capa - self.Sa[k] + self.Sa_t[k]
    self.wbSu_[k] = self.Fa - self.Perc - self. Capa - self.Su[k] + self.Su_t[k]

    self.Eu_[k] = self.Ea
    self.Qu_[k] = self.Qa + self.Qaadd
    self.Fa_[k] = self.Fa
    self.Cap_[k] = self.Cap
    self.Perc_[k] = self.Perc
