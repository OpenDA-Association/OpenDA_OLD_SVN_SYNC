#!/usr/bin/python

# Wflow is Free software, see below:
#
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
Run the wflow_sbm hydrological model..

usage

::

    wflow_sbm [-h][-v level][-F runinfofile][-L logfile][-C casename][-R runId]
          [-c configfile][-T last_step][-S first_step][-s seconds][-W][-E][-N][-U discharge]
          [-P parameter multiplication][-X][-f][-I][-i tbl_dir][-x subcatchId][-u updatecols]
          [-p inputparameter multiplication]

    -F: if set wflow is expected to be run by FEWS. It will determine
        the timesteps from the runinfo.xml file and save the output initial
        conditions to an alternate location. The runinfo.xml file should be located
        in the inmaps directory of the case. Also set fewsrun=1 in the .ini file!

    -X: save state at the end of the run over the initial conditions at the start

    -f: Force overwrite of existing results

    -T: Set last timestep

    -S: Set the start timestep (default = 1)

    -N: No lateral flow, use runoff response function to generate fast runoff

    -s: Set the model timesteps in seconds

    -I: re-initialize the initial model conditions with default

    -i: Set input table directory (default is intbl)

    -x: run for subcatchment only (e.g. -x 1)

    -C: set the name  of the case (directory) to run

    -R: set the name runId within the current case

    -L: set the logfile

    -E: Switch on reinfiltration of overland flow

    -c: name of wflow the configuration file (default: Casename/wflow_sbm.ini).

    -h: print usage information

    -W: If set, this flag indicates that an ldd is created for the water level
        for each timestep. If not the water is assumed to flow according to the
        DEM. Wflow will run a lot slower with this option. Most of the time
        (shallow soil, steep topography) you do not need this option. Also, if you
        need it you migth actually need another model.

    -U: The argument to this option should be a .tss file with measured discharge in
        [m^3/s] which the program will use to update the internal state to match
        the measured flow. The number of columns in this file should match the
        number of gauges.

    -u: list of gauges/columns to use in update. Format:
        -u [1 , 4 ,13]
        The above example uses column 1, 4 and 13
        Note that this also sets the order in which the updating takes place! In
        general specify downstream gauges first.

    -P: set parameter multiply dictionary (e.g: -P {'self.FirstZoneDepth' : 1.2}
        to increase self.FirstZoneDepth by 20%, multiply with 1.2)

    -p: set input parameter (dynamic, e.g. precip) multiply dictionary
        (e.g: -p {'self.Precipitation' : 1.2} to increase Precipitation
        by 20%, multiply with 1.2)

    -v: set verbosity level


$Author: schelle $
$Id: wflow_sbm.py 552 2012-11-27 19:24:09Z schelle $
$Rev: 552 $
"""
import numpy
#import pcrut
import os
import os.path
import shutil, glob
import getopt
try:
    from  wflow.wf_DynamicFramework import *
except ImportError:
    from  wf_DynamicFramework import *
try:
    from  wflow.wflow_funcs import *
except ImportError:
    from  wflow_funcs import *

try:
    from  wflow.wflow_adapt  import *
except ImportError:
    from  wflow_adapt import *

import scipy
import ConfigParser


wflow = "wflow_sbm: "
wflowVersion = "$Revision: 552 $  $Date: 2012-11-27 20:24:09 +0100 (Tue, 27 Nov 2012) $"

updateCols = []


# Dictionary with parameters and multipliers (used in calibration)
multpars = {}
multdynapars = {}
def usage(*args):
    sys.stdout = sys.stderr
    for msg in args: print msg
    print __doc__
    sys.exit(0)



def actEvap_SBM(RootingDepth,WTable, UStoreDepth,FirstZoneDepth, PotTrans,smoothpar):
    """
    Actual evaporation function:

	- first try to get demand from the saturated zone, using the rootingdepth as a limiting factor
	- secondly try to get the remaining water from the unsaturated store

    Input:
        - RootingDepth,WTable, UStoreDepth,FirstZoneDepth, PotTrans

    Output:
        - ActEvap,  FirstZoneDepth,  UStoreDepth ActEvapUStore

    .. todo::

        add option to take length of roots in saturated zone into account

    """


    # Step 1 from saturated zone, use rootingDepth as a limiting factor
    #rootsinWater = WTable < RootingDepth
    #ActEvapSat = ifthenelse(rootsinWater,min(PotTrans,FirstZoneDepth),0.0)
    # new method:
    # use sCurve to determine if the roots are wet.At the moment this ise set
    # to be a 0-1 curve
    wetroots = sCurve(WTable,a=RootingDepth,c=smoothpar)
    ActEvapSat = min(PotTrans * wetroots,FirstZoneDepth)

    FirstZoneDepth = FirstZoneDepth - ActEvapSat
    RestPotEvap = PotTrans - ActEvapSat

    # now try unsat store
    AvailCap = min(1.0,max (0.0,(WTable - RootingDepth)/(RootingDepth + 1.0)))

    #AvailCap = max(0.0,ifthenelse(WTable < RootingDepth,  WTable/RootingDepth,  RootingDepth/WTable))
    MaxExtr = AvailCap  * UStoreDepth
    ActEvapUStore = min(MaxExtr,RestPotEvap,UStoreDepth)
    UStoreDepth = UStoreDepth - ActEvapUStore

    ActEvap = ActEvapSat + ActEvapUStore

    return ActEvap, FirstZoneDepth,  UStoreDepth, ActEvapUStore


def SnowPackHBV (Snow,SnowWater,Precipitation,Temperature,TTI,TT,Cfmax,WHC):
    """
    HBV Type snowpack modelling using a Temperature degree factor. All correction
    factors (RFCF and SFCF) are set to 1. The refreezing efficiency factor is set to 0.05.

    Input:
	- Snow, SnowWater, Precipitation, Temperature

    returns:
	- Snow,SnowMelt,Precipitation
    """

    RFCF= 1.0      # correction factor for rainfall
    CFR= 0.05000   # refreeing efficiency constant in refreezing of freewater in snow
    SFCF= 1.0      # correction factor for snowfall

    RainFrac=ifthenelse(1.0*TTI == 0.0,ifthenelse(Temperature <= TT,scalar(0.0),scalar(1.0)),min((Temperature-(TT-TTI/2))/TTI,scalar(1.0)));
    RainFrac=max(RainFrac,scalar(0.0))               #fraction of precipitation which falls as rain
    SnowFrac=1-RainFrac                    #fraction of precipitation which falls as snow
    Precipitation=SFCF*SnowFrac*Precipitation+RFCF*RainFrac*Precipitation # different correction for rainfall and snowfall

    SnowFall=SnowFrac*Precipitation  #snowfall depth
    RainFall=RainFrac*Precipitation  #rainfall depth
    PotSnowMelt=ifthenelse(Temperature > TT,Cfmax*(Temperature-TT),scalar(0.0)) #Potential snow melt, based on temperature
    PotRefreezing=ifthenelse(Temperature < TT, Cfmax*CFR*(TT-Temperature),0.0)    #Potential refreezing, based on temperature
    Refreezing=ifthenelse(Temperature < TT,min(PotRefreezing,SnowWater),0.0)       #actual refreezing
    # No landuse correction here
    SnowMelt=min(PotSnowMelt,Snow)                                     #actual snow melt
    Snow=Snow+SnowFall+Refreezing-SnowMelt                          #dry snow content
    SnowWater=SnowWater-Refreezing                                    #free water content in snow
    MaxSnowWater=Snow*WHC # Max water in the snow
    SnowWater=SnowWater+SnowMelt+RainFall # Add all water and potentially supersaturate the snowpack
    RainFall = max(SnowWater-MaxSnowWater,0.0) # rain + surpluss snowwater
    SnowWater = SnowWater - RainFall

    return Snow,SnowWater,SnowMelt,RainFall





class WflowModel(DynamicModel):

  def __init__(self, cloneMap,Dir,RunDir,configfile):
      DynamicModel.__init__(self)
      setclone(Dir + "/staticmaps/" + cloneMap)
      self.runId=RunDir
      self.caseName=Dir
      self.Dir = Dir + "/"
      self.configfile = configfile


  def updateRunOff(self):
      """
      Updates the kinematic wave reservoir. Should be run after updates to Q
      """
      self.WaterLevel=(self.Alpha*pow(self.SurfaceRunoff,self.Beta))/self.Bw
      # wetted perimeter (m)
      P=self.Bw+(2*self.WaterLevel)
      # Alpha
      self.Alpha=self.AlpTerm*pow(P,self.AlpPow)
      self.OldKinWaveVolume = self.KinWaveVolume
      self.KinWaveVolume = self.WaterLevel * self.Bw * self.DCL

  def stateVariables(self):
      """
      returns a list of state variables that are essential to the model.
      This list is essential for the resume and suspend functions to work.

      This function is specific for each model and **must** be present.

      - CanopyStorage is any needed for subdaily steps
      """
      states = ['SurfaceRunoff', 'WaterLevel',
                 'FirstZoneDepth',
                 'Snow',
                 'TSoil',
                  'UStoreDepth',
                 'SnowWater','CanopyStorage']

      return states




  def supplyCurrentTime(self):
      """
      gets the current time in seconds after the start of the run
      """
      return self.currentTimeStep() * self.timestepsecs


  def readtblDefault(self,pathtotbl,landuse,subcatch,soil, default):
    """
    First check if a prepared map of the same name is present
    in the staticmaps directory. next try to
    read a tbl file to match a landuse, catchment and soil map. Returns
    the default value if the tbl file is not found.

    Input:
        - pathtotbl,landuse,subcatch,soil, default

    Output:
        - map constructed from tbl file or map with default value
    """

    mapname = os.path.dirname(pathtotbl) + "/../staticmaps/" + os.path.splitext(os.path.basename(pathtotbl))[0]+".map"
    if os.path.exists(mapname):
        self.logger.info("reading map parameter file: " + mapname)
        rest = cover(readmap(mapname),default)
    else:
        if os.path.isfile(pathtotbl):
            rest=lookupscalar(pathtotbl,landuse,subcatch,soil) #
            self.logger.info("Creating map from table: " + pathtotbl)
        else:
            self.logger.warn("tbl file not found (" + pathtotbl + ") returning default value: " + str(default))
            rest = scalar(default)

    return rest

  def suspend(self):

      self.logger.info("Saving initial conditions...")
      self.wf_suspend(self.SaveDir + "/outstate/")

      if self.OverWriteInit:
            self.logger.info("Saving initial conditions over start conditions...")
            self.wf_suspend(self.SaveDir + "/instate/")

      if self.fewsrun:
          self.logger.info("Saving initial conditions for FEWS...")
          self.wf_suspend(self.Dir + "/outstate/")

      report(self.CumInwaterMM,self.SaveDir + "/outsum/CumInwaterMM.map")
      report(self.CumReinfilt,self.SaveDir + "/outsum/CumReinfilt.map")
      report(self.CumPrec,self.SaveDir + "/outsum/CumPrec.map")
      report(self.CumEvap,self.SaveDir + "/outsum/CumEvap.map")
      report(self.CumInt,self.SaveDir + "/outsum/CumInt.map")
      report(self.CumLeakage,self.SaveDir + "/outsum/CumLeakage.map")
      report(self.CumPotenEvap,self.SaveDir + "/outsum/CumPotenEvap.map")
      report(self.CumExfiltWater,self.SaveDir + "/outsum/CumExfiltWater.map")
      report(self.watbal,self.SaveDir + "/outsum/watbal.map")

  def initial(self):

    """Initial part of the model, executed only once """
    global statistics
    global multpars

    self.thestep = scalar(0)
    self.basetimestep = 86400
    self.SSSF=False
    setglobaloption("unittrue")
    intbl = "intbl"
    self.precipTss="/intss/P.tss"
    self.evapTss="/intss/PET.tss"
    self.tempTss="/intss/T.tss"
    self.inflowTss="/intss/Inflow.tss"
    self.SeepageTss="/intss/Seepage.tss"




    self.logger.info("running for " + str(self.nrTimeSteps()) + " timesteps")
    self.setQuiet(True)

        # Set and get defaults from ConfigFile here ###################################
    self.scalarInput = int(configget(self.config,"model","ScalarInput","0"))
    self.Tslice = int(configget(self.config,"model","Tslice","1"))
    self.interpolMethod = configget(self.config,"model","InterpolationMethod","inv")
    self.reinit = int(configget(self.config,"model","reinit","0"))
    self.fewsrun = int(configget(self.config,"model","fewsrun","0"))
    self.OverWriteInit = int(configget(self.config,"model","OverWriteInit","0"))
    self.updating = int(configget(self.config,"model","updating","0"))
    self.updateFile = configget(self.config,"model","updateFile","no_set")

    self.sCatch = int(configget(self.config,"model","sCatch","0"))
    self.intbl = configget(self.config,"model","intbl","intbl")
    self.timestepsecs = int(configget(self.config,"model","timestepsecs","86400"))
    self.modelSnow = int(configget(self.config,"model","ModelSnow","1"))
    sizeinmetres = int(configget(self.config,"layout","sizeinmetres","0"))
    alf = float(configget(self.config,"model","Alpha","60"))
    #TODO: make this into a list for all gauges or a map
    Qmax = float(configget(self.config,"model","AnnualDischarge","300"))
    self.UpdMaxDist =float(configget(self.config,"model","UpdMaxDist","100"))
    self.ExternalQbase=int(configget(self.config,'model','ExternalQbase','0'))
    self.waterdem=int(configget(self.config,'model','waterdem','0'))
    WIMaxScale=float(configget(self.config,'model','WIMaxScale','0.8'))
    self.reInfilt=int(configget(self.config,'model','reInfilt','0'))



    # static maps to use (normally default)
    wflow_subcatch = configget(self.config,"model","wflow_subcatch","staticmaps/wflow_subcatch.map")
    wflow_dem  = configget(self.config,"model","wflow_dem","staticmaps/wflow_dem.map")
    wflow_ldd = configget(self.config,"model","wflow_ldd","staticmaps/wflow_ldd.map")
    wflow_river  = configget(self.config,"model","wflow_river","staticmaps/wflow_river.map")
    wflow_riverlength  = configget(self.config,"model","wflow_riverlength","staticmaps/wflow_riverlength.map")
    wflow_riverlength_fact  = configget(self.config,"model","wflow_riverlength_fact","staticmaps/wflow_riverlength_fact.map")
    wflow_landuse  = configget(self.config,"model","wflow_landuse","staticmaps/wflow_landuse.map")
    wflow_soil  = configget(self.config,"model","wflow_soil","staticmaps/wflow_soil.map")
    wflow_gauges  = configget(self.config,"model","wflow_gauges","staticmaps/wflow_gauges.map")
    wflow_inflow  = configget(self.config,"model","wflow_inflow","staticmaps/wflow_inflow.map")
    wflow_mgauges  = configget(self.config,"model","wflow_mgauges","staticmaps/wflow_mgauges.map")


    # 2: Input base maps ########################################################
    subcatch=ordinal(readmap(self.Dir + wflow_subcatch)) # Determines the area of calculations (all cells > 0)
    subcatch = ifthen(subcatch > 0, subcatch)
    if self.sCatch > 0:
    	subcatch = ifthen(subcatch == sCatch,subcatch)

    self.Altitude=readmap(self.Dir + wflow_dem)# * scalar(defined(subcatch)) # DEM
    self.TopoLdd=readmap(self.Dir + wflow_ldd)        # Local
    self.TopoId=readmap(self.Dir + wflow_subcatch)        # area map
    self.River=cover(boolean(readmap(self.Dir + wflow_river)),0)
    self.RiverLength=pcrut.readmapSave(self.Dir + wflow_riverlength,0.0)
    # Factor to multiply riverlength with (defaults to 1.0)
    self.RiverLengthFac=pcrut.readmapSave(self.Dir + wflow_riverlength_fact,1.0)

    # read landuse and soilmap and make sure there are no missing points related to the
    # subcatchment map. Currently sets the lu and soil type  type to 1
    self.LandUse=readmap(self.Dir + wflow_landuse)
    self.LandUse=cover(self.LandUse,nominal(ordinal(subcatch) > 0))
    self.Soil=readmap(self.Dir + wflow_soil)
    self.Soil=cover(self.Soil,nominal(ordinal(subcatch) > 0))
    self.OutputLoc=readmap(self.Dir + wflow_gauges)        # location of output gauge(s)
    self.InflowLoc=pcrut.readmapSave(self.Dir + wflow_inflow,0.0)  # location abstractions/inflows.
    self.SeepageLoc=pcrut.readmapSave(self.Dir + wflow_inflow,0.0)  # location abstractions/inflows.


    # Experimental
    self.RunoffGenSigmaFunction = int(configget(self.config,'model','RunoffGenSigmaFunction','0'))
    self.RunoffGeneratingGWPerc = float(configget(self.config,'defaultfortbl','RunoffGeneratingGWPerc','0.1'))
    self.RunoffGeneratingThickness = float(configget(self.config,'defaultfortbl','RunoffGeneratingThickness','0.0'))

    if self.scalarInput:
        self.gaugesMap=readmap(self.Dir + wflow_mgauges)        # location of rainfall/evap/temp gauge(s)
    self.OutputId=readmap(self.Dir + wflow_subcatch)       # location of subcatchment
    # Temperature correction poer cell to add

    self.TempCor=pcrut.readmapSave(self.Dir + configget(self.config,"model","TemperatureCorrectionMap","staticmaps/wflow_tempcor.map"),0.0)

    self.ZeroMap=0.0*scalar(subcatch)                    #map with only zero's

    # 3: Input time series ###################################################
    self.P_mapstack=self.Dir + configget(self.config,"inputmapstacks","Precipitation","/inmaps/P") # timeseries for rainfall
    self.PET_mapstack=self.Dir + configget(self.config,"inputmapstacks","EvapoTranspiration","/inmaps/PET") # timeseries for rainfall"/inmaps/PET"          # potential evapotranspiration
    self.TEMP_mapstack=self.Dir + configget(self.config,"inputmapstacks","Temperature","/inmaps/TEMP") # timeseries for rainfall "/inmaps/TEMP"          # global radiation
    self.Inflow_mapstack=self.Dir + configget(self.config,"inputmapstacks","Inflow","/inmaps/IF") # timeseries for rainfall "/inmaps/IF" # in/outflow locations (abstractions)
    self.Seepage_mapstack=self.Dir + configget(self.config,"inputmapstacks","Seepage","/inmaps/SE") # timeseries for rainfall "/inmaps/SE" # in/outflow locations (abstractions)
    self.P = self.ZeroMap


    # Set static initial values here #########################################


    self.SoilAlbedo = 0.1         # Not used at the moment
    self.pi = 3.1416
    self.e = 2.7183
    self.SScale = 100.0

    self.Latitude  =  ycoordinate(boolean(self.Altitude))
    self.Longitude =  xcoordinate(boolean(self.Altitude))

    self.logger.info("Linking parameters to landuse, catchment and soil...")
    self.RunoffGeneratingGWPerc=self.readtblDefault(self.Dir + "/" + self.intbl + "/RunoffGeneratingGWPerc.tbl",self.LandUse,subcatch,self.Soil,self.RunoffGeneratingGWPerc)
    self.RunoffGeneratingThickness=self.readtblDefault(self.Dir + "/" + self.intbl + "/RunoffGeneratingThickness.tbl",self.LandUse,subcatch,self.Soil,self.RunoffGeneratingThickness)
    self.Cmax=self.readtblDefault(self.Dir + "/" + self.intbl + "/MaxCanopyStorage.tbl",self.LandUse,subcatch,self.Soil,1.0)
    self.EoverR=self.readtblDefault(self.Dir + "/" + self.intbl + "/EoverR.tbl",self.LandUse,subcatch,self.Soil,0.1)
    # self.Albedo=lookupscalar(self.Dir + "\intbl\Albedo.tbl",self.LandUse) # Not used anymore
    self.CanopyGapFraction=self.readtblDefault(self.Dir + "/" + self.intbl + "/CanopyGapFraction.tbl",self.LandUse,subcatch,self.Soil,0.1)
    self.RootingDepth=self.readtblDefault(self.Dir + "/" + self.intbl + "/RootingDepth.tbl",self.LandUse,subcatch,self.Soil,750.0) #rooting depth
    #: rootdistpar determien how roots are linked to water table.The number shoudl be negative. A high number means that all roots are wet if
    #: the water table is above the lowest part of the roots. A lower number smooths this.
    self.rootdistpar=self.readtblDefault(self.Dir + "/" + self.intbl + "/rootdistpar.tbl",self.LandUse,subcatch,self.Soil,-80000.0) #rrootdistpar

    # Soil parameters
    # infiltration capacity if the soil [mm/day]
    self.InfiltCapSoil=self.readtblDefault(self.Dir + "/" + self.intbl + "/InfiltCapSoil.tbl",self.LandUse,subcatch,self.Soil,100.0) #
    self.CapScale=self.readtblDefault(self.Dir + "/" + self.intbl + "/CapScale.tbl",self.LandUse,subcatch,self.Soil,100.0) #
    # infiltration capacity of the compacted
    self.InfiltCapPath=self.readtblDefault(self.Dir + "/" + self.intbl + "/InfiltCapPath.tbl",self.LandUse,subcatch,self.Soil,10.0) #
    self.MaxLeakage=self.readtblDefault(self.Dir + "/" + self.intbl + "/MaxLeakage.tbl",self.LandUse,subcatch,self.Soil,0.0) #
    # areas (paths) in [mm/day]
    # Fraction area with compacted soil (Paths etc.)
    self.PathFrac=self.readtblDefault(self.Dir + "/" + self.intbl + "/PathFrac.tbl",self.LandUse,subcatch,self.Soil,0.01)
    # thickness of the soil
    self.FirstZoneThickness = self.readtblDefault(self.Dir + "/" + self.intbl + "/FirstZoneCapacity.tbl",self.LandUse,subcatch,self.Soil,2000.0)
    self.thetaR = self.readtblDefault(self.Dir + "/" + self.intbl + "/thetaR.tbl",self.LandUse,subcatch,self.Soil,0.01)
    self.thetaS = self.readtblDefault(self.Dir + "/" + self.intbl + "/thetaS.tbl",self.LandUse,subcatch,self.Soil,0.6)
    # minimum thickness of soild
    self.FirstZoneMinCapacity = self.readtblDefault(self.Dir + "/" + self.intbl + "/FirstZoneMinCapacity.tbl",self.LandUse,subcatch,self.Soil,500.0)

    # FirstZoneKsatVer = $2\inmaps\FirstZoneKsatVer.map
    self.FirstZoneKsatVer=self.readtblDefault(self.Dir + "/" + self.intbl + "/FirstZoneKsatVer.tbl",self.LandUse,subcatch,self.Soil,3000.0) #
    self.Beta = scalar(0.6) # For sheetflow

    self.M=self.readtblDefault(self.Dir + "/" + self.intbl + "/M.tbl" ,self.LandUse,subcatch,self.Soil,300.0) # Decay parameter in Topog_sbm
    self.N=self.readtblDefault(self.Dir + "/" + self.intbl + "/N.tbl",self.LandUse,subcatch,self.Soil,0.072)  # Manning overland flow
    self.NRiver=self.readtblDefault(self.Dir + "/" + self.intbl + "/N_River.tbl",self.LandUse,subcatch,self.Soil,0.036)  # Manning river
    self.WaterFrac=self.readtblDefault(self.Dir + "/" + self.intbl + "/WaterFrac.tbl",self.LandUse,subcatch,self.Soil,0.0)  # Fraction Open water



    if self.modelSnow:
        # HBV Snow parameters
        # critical temperature for snowmelt and refreezing:  TTI= 1.000
        self.TTI=self.readtblDefault(self.Dir + "/" + self.intbl + "/TTI.tbl" ,self.LandUse,subcatch,self.Soil,1.0)
        # TT = -1.41934 # defines interval in which precipitation falls as rainfall and snowfall
        self.TT=self.readtblDefault(self.Dir + "/" + self.intbl + "/TT.tbl" ,self.LandUse,subcatch,self.Soil,-1.41934)
        #Cfmax = 3.75653 # meltconstant in temperature-index
        self.Cfmax=self.readtblDefault(self.Dir + "/" + self.intbl + "/Cfmax.tbl" ,self.LandUse,subcatch,self.Soil,3.75653)
        # WHC= 0.10000        # fraction of Snowvolume that can store water
        self.WHC=self.readtblDefault(self.Dir + "/" + self.intbl + "/WHC.tbl" ,self.LandUse,subcatch,self.Soil,0.1)
        # Wigmosta, M. S., L. J. Lane, J. D. Tagestad, and A. M. Coleman (2009).
        self.w_soil=self.readtblDefault(self.Dir + "/" +  self.intbl + "/w_soil.tbl",self.LandUse,subcatch,self.Soil,0.9 * 3.0/24.0)  # soil T factor
        self.cf_soil=self.readtblDefault(self.Dir + "/" + self.intbl + "/cf_soil.tbl",self.LandUse,subcatch,self.Soil,0.038)  # Ksat reduction factor fro frozen soi
        #Switched off for nowl
        #self.cf_soil=self.readtblDefault(self.Dir + "/" + intbl + "/cf_soil.tbl",self.LandUse,subcatch,self.Soil,1.00)  # Ksat reduction factor fro frozen soil

    # Determine real slope and cell length

    self.xl,self.yl,self.reallength = pcrut.detRealCellLength(self.ZeroMap,sizeinmetres)
    self.Slope= slope(self.Altitude)
    #self.Slope=ifthen(boolean(self.TopoId),max(0.001,self.Slope*celllength()/self.reallength))
    self.Slope=max(0.001,self.Slope*celllength()/self.reallength)
    Terrain_angle=scalar(atan(self.Slope))


    # Multiply parameters with a factor (for calibration etc) -P option in command line
    for k, v in multpars.iteritems():
        estr = k + "=" + k + "*" + str(v)
        self.logger.info("Parameter multiplication: " +  estr)
        exec estr

    self.N=ifthenelse(self.River, self.NRiver, self.N)

    # TOPOG_SBM type soil stuff
    self.f = (self.thetaS -self.thetaR)/self.M
    # Determine river width from DEM, upstream area and yearly average discharge
    # Scale yearly average Q at outlet with upstream are to get Q over whole catchment
    # Alf ranges from 5 to > 60. 5 for hardrock. large values for sediments
    # "Noah J. Finnegan et al 2005 Controls on the channel width of rivers:
    # Implications for modeling fluvial incision of bedrock"

    upstr = catchmenttotal(1, self.TopoLdd)
    Qscale = upstr/mapmaximum(upstr) * Qmax
    W = (alf * (alf + 2.0)**(0.6666666667))**(0.375) * Qscale**(0.375) * (max(0.0001,windowaverage(self.Slope,celllength() * 4.0)))**(-0.1875) * self.N **(0.375)
    RiverWidth = W


    # soil thickness based on topographical index (see Environmental modelling: finding simplicity in complexity)
    # 1: calculate wetness index
    # 2: Scale the capacity (now actually a max capacity) based on the index, also apply a minmum capacity
    WI = ln(accuflux(self.TopoLdd,1)/self.Slope) # Topographical wetnesss. Scale WI by zone/subcatchment assuming these ara also geological units
    WIMax = areamaximum(WI, self.TopoId) * WIMaxScale
    self.FirstZoneThickness = max(min(self.FirstZoneThickness,(WI/WIMax) * self.FirstZoneThickness),    self.FirstZoneMinCapacity)

    self.FirstZoneCapacity = self.FirstZoneThickness * (self.thetaS -self.thetaR)

    # limit roots to top 99% of first zone
    self.RootingDepth = min(self.FirstZoneThickness * 0.99,self.RootingDepth)

    # subgrid runoff generation
    self.DemMax=readmap(self.Dir + "/staticmaps/wflow_demmax")
    self.DrainageBase=readmap(self.Dir + "/staticmaps/wflow_demmin")
    self.CC = min(100.0,-log(1.0/0.1 - 1)/min(-0.1,self.DrainageBase - self.Altitude))

    if self.RunoffGeneratingThickness <= 0.0:
        self.GWScale = (self.DemMax-self.DrainageBase)/self.FirstZoneThickness / self.RunoffGeneratingGWPerc
    else:
        self.GWScale = (self.DemMax-self.DrainageBase)/min(self.RunoffGeneratingThickness, self.FirstZoneThickness)


    # Which columns/gauges to use/ignore in updating
    self.UpdateMap = self.ZeroMap

    if self.updating:
        touse = numpy.zeros(gaugear.shape,dtype='int')

        for thecol in updateCols:
            idx = (gaugear == thecol).nonzero()
            touse[idx] = thecol


        self.UpdateMap = numpy2pcr(Nominal,touse,0.0)
        # Calulate distance to updating points (upstream) annd use to scale the correction
        # ldddist returns zero for cell at the gauges so add 1.0 tp result
        self.DistToUpdPt = cover(min(ldddist(self.TopoLdd,boolean(cover(self.UpdateMap,0)),1) * self.reallength/celllength(),self.UpdMaxDist),self.UpdMaxDist)



    # Initializing of variables
    self.logger.info("Initializing of model variables..")
    self.TopoLdd=lddmask(self.TopoLdd,boolean(self.TopoId))
    catchmentcells=maptotal(scalar(self.TopoId))

    # Used to seperate output per LandUse/management classes
    OutZones = self.LandUse

    self.QMMConv = self.timestepsecs/(self.reallength * self.reallength * 0.001) #m3/s --> mm
    self.ToCubic = (self.reallength * self.reallength * 0.001) / self.timestepsecs # m3/s
    self.KinWaveVolume=self.ZeroMap
    self.OldKinWaveVolume=self.ZeroMap
    self.sumprecip=self.ZeroMap                          #accumulated rainfall for water balance
    self.sumevap=self.ZeroMap                            #accumulated evaporation for water balance
    self.sumrunoff=self.ZeroMap                          #accumulated runoff for water balance
    self.sumint=self.ZeroMap                             #accumulated interception for water balance
    self.sumleakage=self.ZeroMap
    self.CumReinfilt=self.ZeroMap
    self.sumoutflow=self.ZeroMap
    self.sumsnowmelt=self.ZeroMap
    self.CumRad=self.ZeroMap
    self.SnowMelt=self.ZeroMap
    self.CumPrec=self.ZeroMap
    self.CumInwaterMM=self.ZeroMap
    self.CumInfiltExcess=self.ZeroMap
    self.CumExfiltWater=self.ZeroMap
    self.CumSurfaceWater=self.ZeroMap
    self.CumEvap=self.ZeroMap
    self.CumPotenEvap=self.ZeroMap
    self.CumInt=self.ZeroMap
    self.CumRad=self.ZeroMap
    self.CumLeakage=self.ZeroMap
    self.CumPrecPol=self.ZeroMap
    self.FirstZoneFlux=self.ZeroMap
    self.FreeWaterDepth=self.ZeroMap
    self.SumCellWatBal=self.ZeroMap
    self.PathInfiltExceeded=self.ZeroMap
    self.SoilInfiltExceeded=self.ZeroMap
    self.CumOutFlow=self.ZeroMap
    self.CumCellInFlow=self.ZeroMap
    self.CumIF=self.ZeroMap
    self.CumSeepage=self.ZeroMap
    self.CumActInfilt=self.ZeroMap
    self.Aspect=scalar(aspect(self.Altitude))# aspect [deg]
    self.Aspect  = ifthenelse(self.Aspect <= 0.0 , scalar(0.001),self.Aspect)
    # On Flat areas the Aspect function fails, fill in with average...
    self.Aspect = ifthenelse (defined(self.Aspect), self.Aspect, areaaverage(self.Aspect,self.TopoId))

    # Set DCL to riverlength if that is longer that the basic length calculated from grid
    drainlength = detdrainlength(self.TopoLdd,self.xl,self.yl)

    self.DCL=max(drainlength,self.RiverLength) # m
    # Multiply with Factor (taken from upscaling operation, defaults to 1.0 if no map is supplied
    self.DCL = self.DCL * max(1.0,self.RiverLengthFac)

    # water depth (m)
    # set width for kinematic wave to cell width for all cells
    self.Bw=detdrainwidth(self.TopoLdd,self.xl,self.yl)
    # However, in the main river we have real flow so set the width to the
    # width of the river

    self.Bw=ifthenelse(self.River, RiverWidth, self.Bw)

    # Add rivers to the WaterFrac, but check with waterfrac map
    self.RiverFrac = min(1.0,ifthenelse(self.River,(RiverWidth*self.DCL)/(self.xl*self.yl),0))
    self.WaterFrac = self.WaterFrac - ifthenelse((self.RiverFrac + self.WaterFrac) > 1.0, self.RiverFrac + self.WaterFrac - 1.0, 0.0)


    # term for Alpha
    self.AlpTerm=pow((self.N/(sqrt(self.Slope))),self.Beta)
    # power for Alpha
    self.AlpPow=(2.0/3.0)*self.Beta
    # initial approximation for Alpha


    #self.initstorage=areaaverage(self.FirstZoneDepth,self.TopoId)+areaaverage(self.UStoreDepth,self.TopoId)#+areaaverage(self.Snow,self.TopoId)

    # Define timeseries outputs There seems to be a bug and the .tss files are
    # saved in the current dir...
    tssName = os.path.join(self.Dir, "outtss", "exf")
    self.logger.info("Create timeseries outputs...")

    toprinttss = configsection(self.config,'outputtss')
    for a in toprinttss:
        tssName = self.Dir + "/" + self.runId + "/" +  self.config.get("outputtss",a)
        estr = "self." + self.config.get("outputtss",a) + "Tss=wf_TimeoutputTimeseries('" + tssName + "', self, self.OutputId,noHeader=False)"
        self.logger.info("Creating tss output: " + a + "(" + self.config.get('outputtss',a) + ")")
        exec estr

    self.runTss=wf_TimeoutputTimeseries(self.Dir + "/" + self.runId +  "/run",self, self.OutputLoc,noHeader=False)
    self.levTss=wf_TimeoutputTimeseries(self.Dir + "/" + self.runId  + "/lev",self, self.OutputLoc,noHeader=False)


    # calculate catchmentsize
    self.upsize=catchmenttotal(self.xl * self.yl,self.TopoLdd)
    self.csize=areamaximum(self.upsize,self.TopoId)
    # Save some summary maps
    self.logger.info("Saving summary maps...")
    if self.modelSnow:
        report(self.Cfmax,self.Dir + "/" + self.runId + "/outsum/Cfmax.map")
        report(self.TTI,self.Dir + "/" + self.runId + "/outsum/TTI.map")
        report(self.TT,self.Dir + "/" + self.runId + "/outsum/TT.map")
        report(self.WHC,self.Dir + "/" + self.runId + "/outsum/WHC.map")

    report(self.Cmax,self.Dir + "/" + self.runId + "/outsum/Cmax.map")
    report(self.csize,self.Dir + "/" + self.runId + "/outsum/CatchmentSize.map")
    report(self.upsize,self.Dir + "/" + self.runId + "/outsum/UpstreamSize.map")
    report(self.EoverR,self.Dir + "/" + self.runId + "/outsum/EoverR.map")
    report(self.RootingDepth,self.Dir + "/" + self.runId + "/outsum/RootingDepth.map")
    report(self.CanopyGapFraction,self.Dir + "/" + self.runId + "/outsum/CanopyGapFraction.map")
    report(self.InfiltCapSoil,self.Dir + "/" + self.runId + "/outsum/InfiltCapSoil.map")
    report(self.InfiltCapPath,self.Dir + "/" + self.runId + "/outsum/InfiltCapPath.map")
    report(self.PathFrac,self.Dir + "/" + self.runId + "/outsum/PathFrac.map")
    report(self.thetaR,self.Dir + "/" + self.runId + "/outsum/thetaR.map")
    report(self.thetaS,self.Dir + "/" + self.runId + "/outsum/thetaS.map")
    report(self.FirstZoneMinCapacity,self.Dir + "/" + self.runId + "/outsum/FirstZoneMinCapacity.map")
    report(self.FirstZoneKsatVer,self.Dir + "/" + self.runId + "/outsum/FirstZoneKsatVer.map")
    report(self.M,self.Dir + "/" + self.runId + "/outsum/M.map")
    report(self.FirstZoneCapacity,self.Dir + "/" + self.runId + "/outsum/FirstZoneCapacity.map")
    report(Terrain_angle,self.Dir + "/" + self.runId + "/outsum/angle.map")
    report(self.Slope,self.Dir + "/" + self.runId + "/outsum/slope.map")
    report(WI,self.Dir + "/" + self.runId + "/outsum/WI.map")
    report(self.CC,self.Dir + "/" + self.runId + "/outsum/CC.map")
    report(self.N,self.Dir + "/" + self.runId + "/outsum/N.map")
    report(self.RiverFrac,self.Dir + "/" + self.runId + "/outsum/RiverFrac.map")

    report(self.xl,self.Dir + "/" + self.runId + "/outsum/xl.map")
    report(self.yl,self.Dir + "/" + self.runId + "/outsum/yl.map")
    report(self.reallength,self.Dir + "/" + self.runId + "/outsum/rl.map")
    report(self.DCL,self.Dir + "/" + self.runId + "/outsum/DCL.map")
    report(self.Bw,self.Dir + "/" + self.runId + "/outsum/Bw.map")
    report(ifthen(self.River,self.Bw),self.Dir + "/" + self.runId + "/outsum/RiverWidth.map")
    if self.updating:
        report(self.DistToUpdPt,self.Dir + "/" + self.runId + "/outsum/DistToUpdPt.map")



    self.SaveDir = self.Dir + "/" + self.runId + "/"
    self.logger.info("Starting Dynamic run...")


  def resume(self):

    if self.reinit == 1:
        self.logger.info("Setting initial conditions to default")
        self.FirstZoneDepth =  self.FirstZoneCapacity * 0.85
        self.UStoreDepth =  self.FirstZoneCapacity * 0.0
        self.WaterLevel = self.ZeroMap
        self.SurfaceRunoff = self.ZeroMap
        self.Snow = self.ZeroMap
        self.SnowWater = self.ZeroMap
        self.TSoil = self.ZeroMap + 10.0
        self.CanopyStorage = self.ZeroMap

    else:
        self.logger.info("Setting initial conditions from state files")
        self.wf_resume(self.Dir + "/instate/")

    P=self.Bw+(2.0*self.WaterLevel)
    self.Alpha=self.AlpTerm*pow(P,self.AlpPow)
    self.OldSurfaceRunoff = self.SurfaceRunoff

    self.SurfaceRunoffMM=self.SurfaceRunoff * self.QMMConv
        # Determine initial kinematic wave volume
    self.KinWaveVolume = self.WaterLevel * self.Bw * self.DCL
    self.OldKinWaveVolume = self.KinWaveVolume

    self.SurfaceRunoffMM=self.SurfaceRunoff * self.QMMConv
    self.InitialStorage = self.FirstZoneDepth + self.UStoreDepth
    self.CellStorage = self.FirstZoneDepth + self.UStoreDepth

    # Determine actual water depth
    self.zi = max(0.0,self.FirstZoneThickness - self.FirstZoneDepth/(self.thetaS -self.thetaR))





  def dynamic(self):
    """
    Stuf that is done for each timestep
    """

    self.logger.debug("Step: "+str(int(self.thestep + self._d_firstTimeStep))+"/"+str(int(self._d_nrTimeSteps)))
    self.thestep = self.thestep + 1

    if self.scalarInput:
            # gaugesmap not yet finished. Should be a map with cells that
            # hold the gauges with an unique id
            self.Precipitation = timeinputscalar(self.caseName + self.precipTss,self.gaugesMap)
            if (os.path.exists(self.caseName + self.inflowTss)):
                self.Inflow = cover(timeinputscalar(self.caseName + self.inflowTss,nominal(self.InflowLoc)),0)
            else:
                self.Inflow = self.ZeroMap
            if (os.path.exists(self.caseName + self.SeepageTss)):
                self.Seepage = cover(timeinputscalar(self.caseName + self.SeepageTss,self.SeepageLoc),0)
            else:
                self.Seepage = self.ZeroMap
            self.Precipitation = pcrut.interpolategauges(self.Precipitation,self.interpolMethod)
            self.PotenEvap=timeinputscalar(self.caseName + self.evapTss,self.gaugesMap)
            self.PotenEvap = pcrut.interpolategauges(self.PotenEvap,self.interpolMethod)
            if self.modelSnow:
                self.Temperature=timeinputscalar(self.caseName + self.tempTss,self.gaugesMap)
                self.Temperature = pcrut.interpolategauges(self.Temperature,self.interpolMethod)
                self.Temperature = self.Temperature + self.TempCor
    else:
            self.Precipitation=cover(self.wf_readmap(self.P_mapstack,0.0),0)
            self.PotenEvap=cover(self.wf_readmap(self.PET_mapstack,0.0),0)
            #self.Inflow=cover(self.wf_readmap(self.Inflow),0)
            self.Inflow=pcrut.readmapSave(self.Inflow_mapstack,0.0)
            self.Seepage=pcrut.readmapSave(self.Seepage_mapstack,0.0)
            #self.Inflow=spatial(scalar(0.0))
            if self.modelSnow:
                self.Temperature=cover(self.wf_readmap(self.TEMP_mapstack,0.0),0)
                self.Temperature = self.Temperature + self.TempCor


    # Multiply input parameters with a factor (for calibration etc) -p option in command line
    for k, v in multdynapars.iteritems():
        estr = k + "=" + k + "*" + str(v)
        self.logger.debug("Dynamic Parameter multiplication: " +  estr)
        exec estr

    self.PotEvap = self.PotenEvap #
    #TODO: Snow modelling if enabled _ need to be moved as it breaks the scalar input
    """
    .. todo::

        Snow modelling if enabled _ needs to be moved as it breaks the scalar input
    """
    if self.modelSnow:
            self.TSoil = self.TSoil + self.w_soil * (self.Temperature - self.TSoil) * self.timestepsecs/self.basetimestep
            # return Snow,SnowWater,SnowMelt,RainFall
            self.Snow, self.SnowWater, self.SnowMelt, self.Precipitation = SnowPackHBV(self.Snow,self.SnowWater,self.Precipitation,self.Temperature,self.TTI,self.TT,self.Cfmax,self.WHC)

    ##########################################################################
    # Interception according to a modified Gash model
    # TODOs: add sub-daily interception!
    ##########################################################################

    if self.timestepsecs >= (23 * 3600):
        ThroughFall, Interception, StemFlow, self.CanopyStorage = rainfall_interception_gash(self.Cmax,self.EoverR,self.CanopyGapFraction, self.Precipitation,self.CanopyStorage)
    else:
        NetInterception, ThroughFall, StemFlow, LeftOver, Interception, self.CanopyStorage = rainfall_interception_modrut(self.Precipitation,self.PotEvap,self.CanopyStorage,self.CanopyGapFraction,self.Cmax)

    PotTrans = cover(max(0.0,self.PotEvap - Interception),0.0) # now in mm

    ##########################################################################
    # Start with the soil calculations  ######################################
    ##########################################################################


    self.ExfiltWater=self.ZeroMap
    FreeWaterDepth=self.ZeroMap

    ##########################################################################
    # Determine infiltration into Unsaturated store...########################
    ##########################################################################
    # Add precipitation surplus  FreeWater storage...
    FreeWaterDepth= ThroughFall + StemFlow
    UStoreCapacity = self.FirstZoneCapacity - self.FirstZoneDepth - self.UStoreDepth

    # Runoff onto water boddies and river network
    self.RunoffOpenWater = self.RiverFrac * self.WaterFrac * FreeWaterDepth
    #self.RunoffOpenWater = self.ZeroMap
    FreeWaterDepth = FreeWaterDepth - self.RunoffOpenWater

    if self.RunoffGenSigmaFunction:
        self.AbsoluteGW=self.DemMax-(self.zi*self.GWScale)
        self.SubCellFrac = sCurve(self.AbsoluteGW,c=self.CC,a=self.Altitude+1.0)
        self.SubCellRunoff = self.SubCellFrac * FreeWaterDepth
        self.SubCellGWRunoff = min(self.SubCellFrac * self.FirstZoneDepth, self.SubCellFrac * self.Slope * self.FirstZoneKsatVer * exp(-self.f * self.zi) * self.timestepsecs/self.basetimestep)
        self.FirstZoneDepth=self.FirstZoneDepth-self.SubCellGWRunoff
        FreeWaterDepth = FreeWaterDepth - self.SubCellRunoff
    else:
        self.AbsoluteGW=self.DemMax-(self.zi*self.GWScale)
        self.SubCellFrac = spatial(scalar(0.0))
        self.SubCellGWRunoff = spatial(scalar(0.0))
        self.SubCellRunoff = spatial(scalar(0.0))

    #----->>
    # First determine if the soil infiltration capacity can deal with the
    # amount of water
    # split between infiltration in undisturbed soil and compacted areas (paths)

    SoilInf = FreeWaterDepth * (1- self.PathFrac)
    PathInf = FreeWaterDepth * self.PathFrac
    if self.modelSnow:
        soilInfRedu = ifthenelse(self.TSoil < 0.0 , self.cf_soil, 1.0)
    else:
        soilInfRedu = 1.0
    MaxInfiltSoil= min(self.InfiltCapSoil*soilInfRedu,SoilInf)

    self.SoilInfiltExceeded=self.SoilInfiltExceeded + scalar(self.InfiltCapSoil*soilInfRedu < SoilInf)
    InfiltSoil =  min(MaxInfiltSoil, UStoreCapacity)
    self.UStoreDepth = self.UStoreDepth + InfiltSoil
    UStoreCapacity = UStoreCapacity - InfiltSoil
    FreeWaterDepth = FreeWaterDepth - InfiltSoil
    # <-------
    MaxInfiltPath= min(self.InfiltCapPath*soilInfRedu,PathInf)
    #self.PathInfiltExceeded=self.PathInfiltExceeded + ifthenelse(self.InfiltCapPath < FreeWaterDepth, scalar(1), scalar(0))
    self.PathInfiltExceeded=self.PathInfiltExceeded + scalar(self.InfiltCapPath*soilInfRedu < PathInf)
    InfiltPath = min(MaxInfiltPath, UStoreCapacity)
    self.UStoreDepth = self.UStoreDepth + InfiltPath
    UStoreCapacity = UStoreCapacity - InfiltPath
    FreeWaterDepth = FreeWaterDepth - InfiltPath

    self.ActInfilt = InfiltPath + InfiltSoil

    self.InfiltExcess = ifthenelse (UStoreCapacity > 0.0, FreeWaterDepth, 0.0)
    self.CumInfiltExcess=self.CumInfiltExcess+self.InfiltExcess

    self.ActEvap, self.FirstZoneDepth, self.UStoreDepth, self.ActEvapUStore = actEvap_SBM(self.RootingDepth,self.zi,self.UStoreDepth,self.FirstZoneDepth, PotTrans,self.rootdistpar)
    #self.ActEvap = self.ZeroMap
    #self.ActEvapUStore = self.ZeroMap
    ##########################################################################
    # Transfer of water from unsaturated to saturated store...################
    ##########################################################################
    self.zi = max(0.0,self.FirstZoneThickness - self.FirstZoneDepth/(self.thetaS -self.thetaR)) # Determine actual water depth
    Ksat = self.FirstZoneKsatVer * exp(-self.f * self.zi) * self.timestepsecs/self.basetimestep
    self.DeepKsat = self.FirstZoneKsatVer * exp(-self.f * self.FirstZoneThickness) * self.timestepsecs/self.basetimestep

    # Determine saturation deficit. NB, as noted by Vertessy and Elsenbeer 1997
    # this deficit does NOT take into account the water in the unsaturated zone
    SaturationDeficit =   self.FirstZoneCapacity - self.FirstZoneDepth


    # now the actual tranfer to the saturated store..
    self.Transfer = min(self.UStoreDepth,ifthenelse (SaturationDeficit <= 0.00001, 0.0, Ksat * self.UStoreDepth/(SaturationDeficit+1)))
    # Determine Ksat at base
    #DeepTransfer = min(self.UStoreDepth,ifthenelse (SaturationDeficit <= 0.00001, 0.0, DeepKsat * self.UStoreDepth/(SaturationDeficit+1)))
    ActLeakage = 0.0
    # Now add leakage. to deeper groundwater
    #ActLeakage = cover(max(0,min(self.MaxLeakage* timestepsecs/basetimestep,ActLeakage)),0)

    # Now look if there is Seeapage

    #ActLeakage = ifthenelse(self.Seepage > 0.0, -1.0 * Seepage, ActLeakage)
    self.FirstZoneDepth = self.FirstZoneDepth + self.Transfer - ActLeakage
    self.UStoreDepth = self.UStoreDepth - self.Transfer

    # Determine % saturated
    #Sat = ifthenelse(self.FirstZoneDepth >= (self.FirstZoneCapacity*0.999), scalar(1.0), scalar(0.0))
    self.Sat = max(self.SubCellFrac,scalar(self.FirstZoneDepth >= (self.FirstZoneCapacity*0.999)))
    #PercSat = areaaverage(scalar(Sat),self.TopoId) * 100


    ##########################################################################
    # Horizontal (downstream) transport of water #############################
    ##########################################################################

    if self.waterdem:
        waterDem = self.Altitude - (self.zi * 0.001)
        waterLdd = lddcreate(waterDem,1E35,1E35,1E35,1E35)
        #waterLdd = lddcreate(waterDem,1,1,1,1)
        waterSlope=max(0.00001,slope(waterDem)*celllength()/self.reallength)

    self.zi = max(0.0,self.FirstZoneThickness - self.FirstZoneDepth/(self.thetaS -self.thetaR)) # Determine actual water depth

    if self.waterdem:
        MaxHor =  max(0.0,min(self.FirstZoneKsatVer * waterSlope * exp(-SaturationDeficit/self.M),self.FirstZoneDepth)) * self.timestepsecs/self.basetimestep
        self.FirstZoneFlux = accucapacityflux (waterLdd, self.FirstZoneDepth, MaxHor)
        self.FirstZoneDepth = accucapacitystate (waterLdd, self.FirstZoneDepth, MaxHor)
    else:
        #
        #MaxHor = max(0,min(self.FirstZoneKsatVer * self.Slope * exp(-SaturationDeficit/self.M),self.FirstZoneDepth*(self.thetaS-self.thetaR))) * timestepsecs/basetimestep
        MaxHor =  max(0.0,min(self.FirstZoneKsatVer * self.Slope * exp(-SaturationDeficit/self.M),self.FirstZoneDepth)) * self.timestepsecs/self.basetimestep
        self.FirstZoneFlux = accucapacityflux (self.TopoLdd, self.FirstZoneDepth, MaxHor)
        self.FirstZoneDepth = accucapacitystate (self.TopoLdd, self.FirstZoneDepth, MaxHor)




    ##########################################################################
    # Determine returnflow from first zone          ##########################
    ##########################################################################
    self.ExfiltWaterFrac = sCurve(self.FirstZoneDepth,a=self.FirstZoneCapacity,c=5.0)
    self.ExfiltWater=self.ExfiltWaterFrac  * (self.FirstZoneDepth - self.FirstZoneCapacity)
    #self.ExfiltWater=ifthenelse (self.FirstZoneDepth - self.FirstZoneCapacity > 0 , self.FirstZoneDepth - self.FirstZoneCapacity , 0.0)
    self.FirstZoneDepth=self.FirstZoneDepth - self.ExfiltWater


    # Re-determine UStoreCapacity
    UStoreCapacity = self.FirstZoneCapacity - self.FirstZoneDepth - self.UStoreDepth
    #Determine capilary rise
    self.zi = max(0.0,self.FirstZoneThickness - self.FirstZoneDepth/(self.thetaS -self.thetaR)) # Determine actual water depth
    Ksat = self.FirstZoneKsatVer * exp(-self.f * self.zi) * self.timestepsecs/self.basetimestep

    MaxCapFlux = max(0.0,min(Ksat,self.ActEvapUStore,UStoreCapacity,self.FirstZoneDepth))
    # No capilary flux is roots are in water, max flux if very near to water, lower flux if distance is large
    CapFluxScale = ifthenelse(self.zi > self.RootingDepth, self.CapScale/(self.CapScale + self.zi -self.RootingDepth), 0.0)
    self.CapFlux = MaxCapFlux * CapFluxScale


    self.UStoreDepth = self.UStoreDepth + self.CapFlux
    self.FirstZoneDepth = self.FirstZoneDepth - self.CapFlux

    # org SurfaceWater = self.SurfaceRunoff * self.DCL * self.QMMConv # SurfaceWater (mm) from SurfaceRunoff (m3/s)
    SurfaceWater = self.SurfaceRunoff *  self.QMMConv # SurfaceWater (mm) from SurfaceRunoff (m3/s)
    self.CumSurfaceWater = self.CumSurfaceWater + SurfaceWater

    # Estimate water that may re-infiltrate
    if self.reInfilt:
            Reinfilt = max(0,min(SurfaceWater,min(self.InfiltCapSoil,UStoreCapacity)))
            self.CumReinfilt=self.CumReinfilt + Reinfilt
            self.UStoreDepth = self.UStoreDepth + Reinfilt
    else:
            Reinfilt = self.ZeroMap


    self.InwaterMM=max(0.0,self.ExfiltWater + FreeWaterDepth + self.SubCellRunoff + self.SubCellGWRunoff + self.RunoffOpenWater - Reinfilt)
    self.Inwater=self.InwaterMM * self.ToCubic # m3/s

    self.ExfiltWaterCubic=self.ExfiltWater * self.ToCubic
    self.SubCellGWRunoffCubic = self.SubCellGWRunoff * self.ToCubic
    self.SubCellRunoffCubic = self.SubCellRunoff * self.ToCubic
    self.InfiltExcessCubic = self.InfiltExcess * self.ToCubic
    self.FreeWaterDepthCubic=FreeWaterDepth * self.ToCubic
    self.ReinfiltCubic=-1.0 * Reinfilt * self.ToCubic
    self.Inwater=self.Inwater + self.Inflow # Add abstractions/inflows in m^3/sec

    ##########################################################################
    # Runoff calculation via Kinematic wave ##################################
    ##########################################################################
    # per distance along stream
    q=self.Inwater/self.DCL
    # discharge (m3/s)
    self.SurfaceRunoff = kinematic(self.TopoLdd, self.SurfaceRunoff,q,self.Alpha, self.Beta,self.Tslice,self.timestepsecs,self.DCL) # m3/s
    self.SurfaceRunoffMM=self.SurfaceRunoff*self.QMMConv # SurfaceRunoffMM (mm) from SurfaceRunoff (m3/s)
    self.updateRunOff()
    self.InflowKinWaveCell=upstream(self.TopoLdd,self.SurfaceRunoff)
    self.MassBalKinWave = (self.KinWaveVolume - self.OldKinWaveVolume)/self.timestepsecs  + self.InflowKinWaveCell + self.Inwater - self.SurfaceRunoff

    Runoff=self.SurfaceRunoff

    # Updating
    # --------
    # Assume a tss file with as many columns as outpulocs. Start updating for each non-missing value and start with the
    # first column (nr 1). Assumes that outputloc and columns match!

    if self.updating:
        QM = timeinputscalar(updateFile, self.UpdateMap) * self.QMMConv

        # Now update the state. Just add to the Ustore
        # self.UStoreDepth =  result
        # No determine multiplication ratio for each gauge influence area.
        # For missing gauges 1.0 is assumed (no change).
        # UpDiff = areamaximum(QM,  self.UpdateMap) - areamaximum(self.SurfaceRunoffMM, self.UpdateMap)
        UpRatio = areamaximum(QM,  self.UpdateMap)/areamaximum(self.SurfaceRunoffMM, self.UpdateMap)

        UpRatio = cover(areaaverage(UpRatio,self.TopoId),1.0)
        # Now split between Soil and Kyn  wave
        UpRatioKyn = min(MaxUpdMult,max(MinUpdMult,(UpRatio - 1.0) * UpFrac + 1.0))
        UpRatioSoil = min(MaxUpdMult,max(MinUpdMult,(UpRatio - 1.0) * (1.0 - UpFrac) + 1.0))

        # update/nudge self.UStoreDepth for the whole upstream area,
        # not sure how much this helps or worsens things
        if UpdSoil:
            toadd = min((self.UStoreDepth * UpRatioSoil) - self.UStoreDepth,StorageDeficit * 0.95)
            self.UStoreDepth = self.UStoreDepth + toadd

        # Update the kinematic wave reservoir up to a maximum upstream distance
        # TODO:  add (much smaller) downstream updating also?
        MM = (1.0 - UpRatioKyn)/self.UpdMaxDist
        UpRatioKyn = MM * self.DistToUpdPt + UpRatioKyn

        self.SurfaceRunoff = self.SurfaceRunoff *  UpRatioKyn
        self.SurfaceRunoffMM=self.SurfaceRunoff*self.QMMConv # SurfaceRunoffMM (mm) from SurfaceRunoff (m3/s)
        self.updateRunOff()

        Runoff=self.SurfaceRunoff

    ##########################################################################
    # water balance ###########################################
    ##########################################################################

    # Single cell based water budget
    CellStorage = self.UStoreDepth+self.FirstZoneDepth
    DeltaStorage = CellStorage - self.InitialStorage
    OutFlow = self.FirstZoneFlux
    CellInFlow = upstream(self.TopoLdd,scalar(self.FirstZoneFlux));
    #CellWatBal = ActInfilt - self.ActEvap - self.ExfiltWater - ActLeakage + Reinfilt + IF - OutFlow + (OldCellStorage - CellStorage)
    #SumCellWatBal = SumCellWatBal + CellWatBal;

    self.CumOutFlow = self.CumOutFlow + OutFlow
    self.CumActInfilt = self.CumActInfilt + self.ActInfilt
    self.CumCellInFlow = self.CumCellInFlow  + CellInFlow
    self.CumPrec=self.CumPrec+self.Precipitation
    self.CumEvap=self.CumEvap+self.ActEvap
    self.CumPotenEvap=self.CumPotenEvap+PotTrans
    self.CumInt=self.CumInt+Interception
    self.CumLeakage=self.CumLeakage+ActLeakage
    self.CumInwaterMM=self.CumInwaterMM+self.InwaterMM
    self.CumExfiltWater=self.CumExfiltWater+self.ExfiltWater
    # Water budget
    #self.watbal = self.CumPrec- self.CumEvap - self.CumInt - self.CumInwaterMM - DeltaStorage  - self.CumOutFlow + self.CumIF
    #self.watbal = self.CumActInfilt  - self.CumEvap - self.CumExfiltWater - DeltaStorage - self.CumOutFlow + self.CumIF
    self.watbal = self.CumPrec + self.CumCellInFlow - self.CumOutFlow- self.CumEvap - self.CumLeakage - self.CumInwaterMM - self.CumInt - DeltaStorage + self.CumReinfilt

    # TODOL bring timeseries export also to the framework
    # sample timeseries
    # Do runoff always
    self.runTss.sample(Runoff)
    self.levTss.sample(self.WaterLevel)


    # Get rest from ini file
    toprinttss = configsection(self.config,'outputtss')
    for a in toprinttss:
        estr = "self." + self.config.get("outputtss",a) + "Tss.sample(" + a +")"
        eval(estr)

    # Print .ini defined outputmaps per timestep
    #toprint = configsection(self.config,'outputmaps')
    #for a in toprint:
    #    eval("self.report(" + a  + ", self.Dir + \"/\" + self.runId + \"/outmaps/" + self.config.get("outputmaps",a) +"\")")



def main():

    """
    Perform command line execution of the model.
    """
    caseName = "default_sbm"
    global multpars
    runId = "run_default"
    configfile="wflow_sbm.ini"
    _lastTimeStep = 0
    _firstTimeStep = 1
    fewsrun=False
    runinfoFile="runinfo.xml"
    timestepsecs=86400
    wflow_cloneMap = 'wflow_subcatch.map'
    NoOverWrite=1

    ## Main model starts here
    ########################################################################
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'XF:L:hC:Ii:v:S:T:WNR:u:s:EP:p:Xx:U:fOc:')
    except getopt.error, msg:
        pcrut.usage(msg)


    for o, a in opts:
        if o == '-F':
            runinfoFile = a
            fewsrun = True
        if o == '-P':
            exec ("multpars =" + a,globals(), globals())
        if o == '-p':
            exec "multdynapars =" + a
            exec ("multdynapars =" + a,globals(), globals())
        if o == '-C': caseName = a
        if o == '-R': runId = a
        if o == '-c': configfile = a
        if o == '-s': timestepsecs = int(a)
        if o == '-T': _lastTimeStep=int(a)
        if o == '-S': _firstTimeStep=int(a)
        if o == '-h': usage()
        if o == '-f': NoOverWrite = 0



    if fewsrun:
        _lastTimeStep =  getTimeStepsfromRuninfo(runinfoFile) * 86400/timestepsecs
        _firstTimeStep = 1

    if _lastTimeStep < _firstTimeStep:
	usage()

    myModel = WflowModel(wflow_cloneMap, caseName,runId,configfile)
    dynModelFw = wf_DynamicFramework(myModel, _lastTimeStep,firstTimestep=_firstTimeStep)
    dynModelFw.createRunId(NoOverWrite=NoOverWrite)

    for o, a in opts:
        if o == '-X': configset(myModel.config,'model','OverWriteInit','1',overwrite=True)
        if o == '-I': configset(myModel.config,'model','reinit','1',overwrite=True)
        if o == '-i': configset(myModel.config,'model','intbl',a,overwrite=True)
        if o == '-s': configset(myModel.config,'model','timestepsecs',a,overwrite=True)
        if o == '-x': configset(myModel.config,'model','sCatch',a,overwrite=True)
        if o == '-c': configset(myModel.config,'model','configfile', a,overwrite=True)
        if o == '-M': configset(myModel.config,'model','MassWasting',"1",overwrite=True)
        if o == '-N': configset(myModel.config,'model','nolateral','1',overwrite=True)
        if o == '-Q': configset(myModel.config,'model','ExternalQbase','1',overwrite=True)
        if o == '-U':
            configset(myModel.config,'model','updateFile',a,overwrite=True)
            configset(myModel.config,'model','updating',"1",overwrite=True)
        if o == '-u':
            print a
            exec "updateCols =" +  a
        if o == '-E': configset(myModel.config,'model','reInfilt','1',overwrite=True)
        if o == '-R': runId = a
        if o == '-W': configset(myModel.config,'model','waterdem','1',overwrite=True)


    dynModelFw._runInitial()
    dynModelFw._runResume()
    dynModelFw._runDynamic(_firstTimeStep,_lastTimeStep)
    dynModelFw._runSuspend()

    fp = open(caseName + "/" + runId + "/runinfo/configofrun.ini",'wb')
    myModel.config.write(fp )



if __name__ == "__main__":
    main()
