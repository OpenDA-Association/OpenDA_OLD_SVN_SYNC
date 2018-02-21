# Copyright (c) J. Schellekens 2005-2011
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
wflow_funcs -  hydrological functions library
---------------------------------------------

In addition this library contain a number of hydrological functions
that may be used within the wflow models

"""


from numpy import *
import getopt
import os
import os.path
import sys


from pcraster import *
from pcraster.framework import *


#import scipy


def rainfall_interception_hbv(Rainfall,PotEvaporation,Cmax,InterceptionStorage):
    """
    Returns:
    TF, Interception, IntEvap,InterceptionStorage
    """
    Interception=min(Rainfall,Cmax-InterceptionStorage)#: Interception in mm/timestep

    InterceptionStorage=InterceptionStorage+Interception #: Current interception storage
    TF=Rainfall-Interception
    IntEvap=min(InterceptionStorage,PotEvaporation) 	 #: Evaporation from interception storage
    InterceptionStorage=InterceptionStorage-IntEvap

    return TF,Interception,IntEvap,InterceptionStorage


def rainfall_interception_gash(Cmax,EoverR,CanopyGapFraction, Precipitation, CanopyStorage,maxevap=9999):
    """
    Interception according to the Gash model (For daily timesteps).
    """
    #TODO:  add other rainfall interception method (lui)
    #TODO: Include subdaily Gash model
    #TODO: add LAI variation in year
    # Hack for stemflow

    pt = 0.1 * CanopyGapFraction

    P_sat = max(scalar(0.0),cover((-Cmax / EoverR) * ln (1.0 - (EoverR/(1.0 - CanopyGapFraction - pt))),scalar(0.0)))

    # large storms P > P_sat

    Iwet = ifthenelse(Precipitation > P_sat, ((1 - CanopyGapFraction - pt) * P_sat) - Cmax, Precipitation * (1 - CanopyGapFraction - pt))
    Isat = ifthenelse(Precipitation > P_sat,(EoverR) * (Precipitation - P_sat), 0.0)

    Idry = ifthenelse (Precipitation > P_sat,  Cmax, 0.0)
    Itrunc = 0

    StemFlow=pt * Precipitation

    ThroughFall = Precipitation- Iwet - Idry- Isat - Itrunc - StemFlow
    Interception = Iwet + Idry + Isat + Itrunc

    # No corect for area without any Interception (say open water Cmax -- zero)
    ThroughFall=ifthenelse(Cmax <= scalar(0.0), Precipitation,ThroughFall)
    Interception=ifthenelse(Cmax <= scalar(0.0), scalar(0.0),Interception)
    StemFlow=ifthenelse(Cmax <= scalar(0.0), scalar(0.0),StemFlow)

    # Now corect for amximum potential evap
    OverEstimate = ifthenelse(Interception > maxevap,Interception - maxevap,scalar(0.0))
    Interception = min(Interception,maxevap)
    # Add surpluss to the thoughdfall
    ThroughFall = ThroughFall + OverEstimate

    return ThroughFall, Interception, StemFlow, CanopyStorage



def rainfall_interception_modrut(Precipitation,PotEvap,CanopyStorage,CanopyGapFraction,Cmax):
    """
    Interception according to a modified Rutter model. The model is solved
    explicitly and there is no drainage below Cmax.

    Returns:
        - NetInterception: P - TF - SF (may be different from the actual wet canopy evaporation)
        - ThroughFall:
        - StemFlow:
        - LeftOver: Amount of potential eveporation not used
        - Interception: Actual wet canopy evaporation in this thimestep
        - CanopyStorage: Canopy storage at the end of the timestep

    """

    ##########################################################################
    # Interception according to a modified Rutter model with hourly timesteps#
    ##########################################################################

    p = CanopyGapFraction
    pt = 0.1 * p

    # Amount of P that falls on the canopy
    Pfrac = (1 - p -pt) * Precipitation

    # S cannot be larger than Cmax, no gravity drainage below that
    DD = ifthenelse (CanopyStorage > Cmax , Cmax - CanopyStorage , 0.0)
    CanopyStorage = CanopyStorage - DD

    # Add the precipitation that falls on the canopy to the store
    CanopyStorage = CanopyStorage + Pfrac

    # Now do the Evap, make sure the store does not get negative
    dC = -1 * min(CanopyStorage, PotEvap)
    CanopyStorage = CanopyStorage + dC

    LeftOver = PotEvap +dC; # Amount of evap not used


    # Now drain the canopy storage again if needed...
    D = ifthenelse (CanopyStorage > Cmax , CanopyStorage - Cmax , 0.0)
    CanopyStorage = CanopyStorage - D

    # Calculate throughfall
    ThroughFall = DD + D + p * Precipitation
    StemFlow = Precipitation * pt

    # Calculate interception, this is NET Interception
    NetInterception = Precipitation - ThroughFall - StemFlow
    Interception = -dC

    return NetInterception, ThroughFall, StemFlow, LeftOver, Interception, CanopyStorage



# baseflow seperation methods
# see http://mssanz.org.au/MODSIM97/Vol%201/Chapman.pdf

def bf_oneparam(discharge, k):
    bf = range(0,len(discharge))
    for i in range(1,len(discharge)):
        bf[i] = (k*bf[i-1]/(2.0-k)) + ((1.0-k)*discharge[i]/(2.0-k))
        if bf[i] > discharge[i]:
            bf[i] = discharge[i]

    return bf


def bf_twoparam(discharge, k,C):
    bf = range(0,len(discharge))
    for i in range(1,len(discharge)):
        bf[i] = (k*bf[i-1]/(1.0+C)) + ((C)*discharge[i]/(1.0+C))
        if bf[i] > discharge[i]:
            bf[i] = discharge[i]

    return bf


def bf_threeparam(discharge, k,C,a):
    bf = range(0,len(discharge))
    for i in range(1,len(discharge)):
        bf[i] = (k*bf[i-1]/(1.0+C)) + ((C)*discharge[i] + a*discharge[i-1]/(1.0+C))
        if bf[i] > discharge[i]:
            bf[i] = discharge[i]

    return bf



