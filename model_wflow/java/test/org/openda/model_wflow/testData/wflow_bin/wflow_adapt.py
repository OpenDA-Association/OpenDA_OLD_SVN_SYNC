# Test version of wflow Delft-FEWS adapter
#
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
wflow_adapt.py: Simple wflow Delft-FEWS adapter in python. This file can be run
as a script from the command-line or be used as a module that provides (limited)
functionality for converting PI-XML files to .tss and back.

*Usage pre adapter:*

**wflow_adapt** -M Pre -t InputTimeseriesXml -I inifile -T timestepInSeconds

*Usage postadapter:*

**wflow_adapt**-M Post -t InputTimeseriesXml -s inputStateFile -I inifile
              -o outputStateFile -r runinfofile -w workdir -C case -T timestepInSeconds

Issues:

- Delft-Fews exports data from 0 to timestep. PCraster starts to count at 1.
  Renaming the files is not desireable. The solution is the add a delay of 1
  timestep in the GA run that exports the mapstacks to wflow.
- Not tested very well.
- There is a considerable amount of duplication (e.g. info in the runinfo.xml and
  the .ini file that you need to specify again :-())

 .. todo::

     rewrite and simplify

$Author: schelle $
$Id: wflow_adapt.py 557 2012-11-29 08:18:28Z schelle $
$Rev: 557 $

"""

import getopt, sys, os
import xml.parsers.expat as expat
from xml.etree.ElementTree import *
from datetime import *
import time
import string

import shutil
import re
from glob import *
import logging
import logging.handlers
import ConfigParser

try:
    import  wflow.wflow_lib as wflow_lib
    import wflow.pcrut as pcrut
except ImportError:
    import  wflow_lib  as wflow_lib
    import  pcrut as pcrut


outMaps = ["run.xml","lev.xml"]
iniFile = "wflow_sbm.ini"
case = "not_set"

logfile = "wflow_adapt.log"

def make_uniek(seq, idfun=None):
    # Order preserving
    return list(_f10(seq, idfun))

def _f10(seq, idfun=None):
    seen = set()
    if idfun is None:
        for x in seq:
            if x in seen:
                continue
            seen.add(x)
            yield x
    else:
        for x in seq:
            x = idfun(x)
            if x in seen:
                continue
            seen.add(x)
            yield x


fewsNamespace="http://www.wldelft.nl/fews/PI"

def setlogger(logfilename):
    """
    Set-up the logging system and return a logger object. Exit if this fails

    Input:
    - filename

    Output:
    - Logger object
    """
    try:
        #create logger
        logger = logging.getLogger("wflow_adapt")
        logger.setLevel(logging.DEBUG)
        ch = logging.handlers.RotatingFileHandler(logfile,maxBytes=200000, backupCount=5)
        #ch = logging.handlers.FileHandler(logfiles,mode='w')
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        ch.setLevel(logging.DEBUG)
        #create formatter
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        #add formatter to ch
        ch.setFormatter(formatter)
        console.setFormatter(formatter)
        #add ch to logger
        logger.addHandler(ch)
        logger.addHandler(console)
        logger.debug("File logging to " + logfilename)
        return logger
    except IOError:
        print "ERROR: Failed to initialize logger with logfile: " + logfilename
        sys.exit(2)



def pixml_state_updateTime(inxml,outxml,DT):
    """
    Reads the pi-state xml file inxml and updates the data/time of
    the state using datetime. Writes updated file to outxml

    - Can be use in scripts to set the date.time of the
      output state.xml that Delft-FEWS writes.

    .. warning::

	This function does not fully parse the xml file and will only work properly
        if the xml files date the dateTime element written on one line.

    """

    if os.path.exists(inxml):
        file = open(inxml, "r")
        all = file.readlines()
        ofile = open(outxml,'w')
        datestr = DT.strftime('%Y-%m-%d')
        timestr = DT.strftime('%H:%M:%S')

        for aline in all:
            pos = aline.find('dateTime')
            if pos >= 0:
                ofile.write("<dateTime date=\"" + datestr + "\" time=\"" + timestr + "\"/>\n")
            else:
                ofile.write(aline.replace('instate','outstate'))


        ofile.close()
    else:
        print inxml + " does not exists."



def pixml_totss_dates (nname,outputdir):
    """
    Gets Date/time info from XML file and creates .tss files with:

        - Day of year
        - Hour of day
        - Others may follow

    """
    if os.path.exists(nname):
        file = open(nname, "r")
        tree = parse(file)
        PItimeSeries = tree.getroot()
        series = PItimeSeries.findall('.//{' + fewsNamespace + '}series')

        events = series[0].findall('.//{' + fewsNamespace + '}event')
        f = open(outputdir + '/YearDay.tss','w')
        ff = open(outputdir + '/Hour.tss','w')
        # write the header
        f.write('Parameter YearDay taken from ' + nname + '\n')
        ff.write('Parameter Hour taken from ' + nname + '\n')
        f.write('2\n')
        ff.write('2\n')
        for i in range(1,3):
            f.write('Data column ' + str(i) + '\n')
            ff.write('Data column ' + str(i) + '\n')
        i=1
        for ev in events:
            dt = datetime.strptime(ev.attrib['date'] + ev.attrib['time'],'%Y-%m-%d%H:%M:%S')
            f.write(str(i) +'\t' + dt.strftime('%j\n'))
            ff.write(str(i) +'\t' + dt.strftime('%H\n'))
            i = i+1
    else:
        print nname + " does not exists."


def pixml_totss(nname,outputdir):
    """
    Converts and PI xml timeseries file to a number of tss files.

    The tss files are created using the following rules:

        - tss filename determined by the content of the parameter element with a ".tss" postfix
        - files are created in "outputdir"
        - multiple locations will be multiple columns in the tss file written in order
          of appearance in the XML file

    """

    if os.path.exists(nname):
        file = open(nname, "r")
        tree = parse(file)
        PItimeSeries = tree.getroot()
        seriesStationList=PItimeSeries.findall('.//{' + fewsNamespace + '}stationName')
        LocList=[]
        for station in seriesStationList:
            LocList.append(station.text)

        Parameters=PItimeSeries.findall('.//{' + fewsNamespace + '}parameterId')
        ParList=[]
        for par in Parameters:
            ParList.append(par.text)


        uniqueParList=make_uniek(ParList)

        colsinfile=len(ParList)

        series = PItimeSeries.findall('.//{' + fewsNamespace + '}series')

        # put whole lot in a dictionary
        val = {}
        parlocs = {}
        i = 0
        for par in uniqueParList:
            parlocs[par] = 1


        for thisS in series:
            par = thisS.find('.//{' + fewsNamespace + '}parameterId').text
            events = thisS.findall('.//{' + fewsNamespace + '}event')
            locs = thisS.findall('.//{' + fewsNamespace + '}locationId')

            i=0;
            for ev in events:
                parlocs[par] = 1
                if val.has_key((i,par)):
                    theval = val[i,par] + '\t' + ev.attrib['value']
                    val[i,par] = theval
                    parlocs[par] = parlocs[par] + 1
                else:
                    val[i,par] = ev.attrib['value']
                i = i+1
        nrevents = i

        for par in uniqueParList:
            f = open(outputdir + '/' + par + '.tss','w')
            # write the header
            f.write('Parameter ' + par + ' taken from ' + nname + '\n')
            f.write(str(colsinfile + 1) + '\n')
            f.write('Timestep\n')
            for i in range(0,colsinfile):
                f.write('Data column ' + str(i) + '\n')
            for i in range(0,nrevents):
                f.write(str(i+1) + '\t' + val[i,par] + '\n')

    else:
        print nname + " does not exists."



def tss_topixml(tssfile,xmlfile,locationname,parametername,Sdate,timestep):
    """
    Converts a .tss file to a PI-xml file

    """

    try:
        tss,header = pcrut.readtss(tssfile)
    except:
        logger.error("Tss file not found: ", tssfile)
        return

    trange = timedelta(seconds=timestep * (tss.shape[0]))
    # The tss have one timeste less as the mapstacks
    extraday = timedelta(seconds=timestep)
    #extraday = timedelta(seconds=0)
    Sdate = Sdate + extraday
    Edate = Sdate + trange - extraday


    Sdatestr = Sdate.strftime('%Y-%m-%d')
    Stimestr = Sdate.strftime('%H:%M:%S')


    Edatestr = Edate.strftime('%Y-%m-%d')
    Etimestr = Edate.strftime('%H:%M:%S')
    ofile = open(xmlfile,'w')
    ofile.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
    ofile.write("<TimeSeries xmlns=\"http://www.wldelft.nl/fews/PI\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:schemaLocation=\"http://www.wldelft.nl/fews/PI http://fews.wldelft.nl/schemas/version1.0/pi-schemas/pi_timeseries.xsd\" version=\"1.2\">\n")
    ofile.write("<timeZone>0.0</timeZone>\n")
    count = 0
    for col in tss.transpose():
        count = count + 1
        ofile.write("<series>\n")
        ofile.write("<header>\n")
        ofile.write("<type>instantaneous</type>\n")
        ofile.write("<locationId>" + header[count-1] + "</locationId>\n")
        ofile.write("<parameterId>" + parametername + "</parameterId>\n")
        ofile.write("<timeStep unit=\"second\" multiplier=\"" + str(timestep) + "\"/>\n")
        ofile.write("<startDate date=\"" + Sdatestr +"\" time=\""+ Stimestr + "\"/>\n")
        ofile.write("<endDate date=\"" + Edatestr + "\" time=\"" + Etimestr + "\"/>\n")
        ofile.write("<missVal>-999.0</missVal>\n")
        ofile.write("<stationName>" + header[count-1] +  "</stationName>\n")
        ofile.write("</header>\n")
        # add data here
        xdate = Sdate
        for pt in col:
            Sdatestr = xdate.strftime('%Y-%m-%d')
            Stimestr = xdate.strftime('%H:%M:%S')
            ofile.write("<event date=\"" + Sdatestr + "\" time=\"" + Stimestr + "\" value=\"" + str(pt) + "\" />\n")
            xdate = xdate + timedelta(seconds=timestep)
        ofile.write("</series>\n")

    ofile.write("</TimeSeries>\n")
    ofile.close()

    return tss

def mapstackxml(mapstackxml,mapstackname,locationname,parametername,Sdate,Edate,timestepsecs):
    """
    writes mapstack xml file
    """
    Sdatestr = Sdate.strftime('%Y-%m-%d')
    Stimestr = Sdate.strftime('%H:%M:%S')
    Edatestr = Edate.strftime('%Y-%m-%d')
    Etimestr = Edate.strftime('%H:%M:%S')
    ofile = open(mapstackxml,'w')
    ofile.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
    ofile.write("<MapStacks xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xmlns=\"http://www.wldelft.nl/fews/PI\" xsi:schemaLocation=\"http://www.wldelft.nl/fews/PI http://fews.wldelft.nl/schemas/version1.0/pi-schemas/pi_mapstacks.xsd\" version=\"1.2\">\n")
    ofile.write("<geoDatum>WGS 1984</geoDatum>\n")
    ofile.write("<timeZone>0.0</timeZone>\n")
    ofile.write("<mapStack>\n")
    ofile.write("<locationId>"+locationname+"</locationId>\n")
    ofile.write("<parameterId>"+parametername+"</parameterId>\n")
    ofile.write("<timeStep unit=\"second\" multiplier=\"" + str(timestepsecs) + "\"/>\n")
    ofile.write("<startDate date=\""+Sdatestr+"\" time=\""+Stimestr+"\"/>\n")
    ofile.write("<endDate date=\""+Edatestr+"\" time=\""+Etimestr+"\"/>\n")
    ofile.write("<file>\n")
    ofile.write("    <pcrgrid file=\""+mapstackname+"\"/>\n")
    ofile.write("</file>\n")
    ofile.write("</mapStack>\n")
    ofile.write("</MapStacks>\n")
    ofile.close()

def getTimeStepsfromRuninfo(xmlfile):
    """
    Gets the number of daily timesteps from the FEWS runinfo file.
    """
    if os.path.exists(xmlfile):
        file = open(xmlfile, "r")
        tree = parse(file)
        runinf = tree.getroot()
        sdate=runinf.find('.//{' + fewsNamespace + '}startDateTime')
        edate=runinf.find('.//{' + fewsNamespace + '}endDateTime')
        sd = datetime.strptime(sdate.attrib['date'] + sdate.attrib['time'],'%Y-%m-%d%H:%M:%S')
        ed = datetime.strptime(edate.attrib['date'] + edate.attrib['time'],'%Y-%m-%d%H:%M:%S')
        diff = ed - sd
        return diff.days # Should actually be + 1 but fews starts at 0!
    else:
        print xmlfile + " does not exists."


def getEndTimefromRuninfo(xmlfile):
    """
    Gets the endtime of the run from the FEWS runinfo file
    """
    if os.path.exists(xmlfile):
        file = open(xmlfile, "r")
        tree = parse(file)
        runinf = tree.getroot()
        edate=runinf.find('.//{' + fewsNamespace + '}endDateTime')
        ed = datetime.strptime(edate.attrib['date'] + edate.attrib['time'],'%Y-%m-%d%H:%M:%S')
    else:
        print xmlfile + " does not exists."

    return ed

def getStartTimefromRuninfo(xmlfile):
    """
    Gets the starttime from the FEWS runinfo file
    """
    if os.path.exists(xmlfile):
        file = open(xmlfile, "r")
        tree = parse(file)
        runinf = tree.getroot()
        edate=runinf.find('.//{' + fewsNamespace + '}startDateTime')
        ed = datetime.strptime(edate.attrib['date'] + edate.attrib['time'],'%Y-%m-%d%H:%M:%S')
    else:
        print xmlfile + " does not exists."

    return ed

def getMapStacksFromRuninfo(xmlfile):
    """
    Gets the list of mapstacks fews expect from the runinfo file and create those
    """

    if os.path.exists(xmlfile):
        file = open(xmlfile, "r")
        tree = parse(file)
        runinf = tree.getroot()
        edate=runinf.find('.//{' + fewsNamespace + '}startDateTime')
        ed = datetime.strptime(edate.attrib['date'] + edate.attrib['time'],'%Y-%m-%d%H:%M:%S')
    else:
        print xmlfile + " does not exists."

    return ed

def pre_adapter(INxmlTimeSeries):
    list_xmlTimeSeries = INxmlTimeSeries.split()
    for xmlTimeSeries in list_xmlTimeSeries:
        pixml_totss(case + '/intss/' + xmlTimeSeries,case + '/intss/')
        pixml_totss_dates(case + '/intss/' + xmlTimeSeries,case + '/intss/')
        #writeNrTimesteps()

def usage():
    print "wflow_adapter -M Pre -t InputTimeseriesXml -I inifile"
    print "wflow_adapter -M run -I inifile -r runinfofile"
    print "wflow_adapter -M Post -t InputTimeseriesXml -s inputStateFile -I inifile"
    print "              -o outputStateFile -r runinfofile -w workdir -C case"
    print " Options:     -T timestepInSeconds"


def main():
    """
    Main entry for using the module as a command line program (e.g. from the Delft-FEWS GA)

    """
    global case
    timestepsecs = 86400

    try:
        opts, args = getopt.getopt(sys.argv[1:], "-T:-M:-t:-s:-o:-r:-w:-C:-I:")
    except getopt.GetoptError, err:
        # print help information and exit:
        print str(err)
        usage()
        sys.exit(2)

    xmlTimeSeries = ""
    stateFile = ""

    mode = "Pre"
    for o, a in opts:
        if o == "-v":
            verbose = True
        elif o in ("-t"):
            xmlTimeSeries = a
        elif o in ("-T"):
            timestepsecs = int(a)
        elif o in ("-o"):
            stateFile = a
        elif o in ("-s"):
            inputStateFile = a
        elif o in ("-r"):
            runinfofile = a
        elif o in ("-w"):
            workdir = a
        elif o in ("-C"):
            case = a
        elif o in ("-I"):
            iniFile = a
        elif o in ("-M"):
            mode = a
        else:
            assert False, "unhandled option"


    # Try and read config file and set default options
    config = ConfigParser.SafeConfigParser()
    config.optionxform = str
    config.read(case + "/" + iniFile)

    # get timestep from wflow ini use comand-line as default
    timestepsecs = int(wflow_lib.configget(config,"model","timestepsecs",str(timestepsecs)))


    logger = setlogger(logfile)

    if mode =="Pre":
        pre_adapter(xmlTimeSeries)
        sys.exit(0)
    elif mode == "Run":
        logger.info("Run adapter not implemented...")    # Not implmented -> se pcraster adapter
        sys.exit(1)
    elif mode == "Post":

        logger.info("Starting postadapter")
        pixml_state_updateTime(inputStateFile,stateFile,getEndTimefromRuninfo(runinfofile))


        # Get outpumapstacks from wflow ini
        mstacks  = config.options('outputmaps')


        for a in mstacks:
           var = config.get("outputmaps",a)
           logger.debug("Creating mapstack xml: " + workdir + "/" + case +"/run_default/outmaps/" + var + ".xml" )
           mapstackxml(workdir + "/" + case +"/run_default/outmaps/" + var +".xml",var + "?????.???",var,var,getStartTimefromRuninfo(runinfofile),getEndTimefromRuninfo(runinfofile),timestepsecs)


        # Back hack to work around the 0 based FEWS problem and create a double timestep zo that we have connection between subsequent runs in FEWS
        #TODO: do the copy for all variable that wflow saves.This hack only works for variable that are saved as states
        shutil.copy(workdir + "/" + case +"/instate/SurfaceRunoff.map",workdir +  "/" + case +"/run_default/outmaps/run00000.000")
        shutil.copy(workdir + "/" + case +"/instate/WaterLevel.map",workdir +  "/" + case +"/run_default/outmaps/lev00000.000")

        # now check for tss files and convert to XML
        tssfiles  = config.options('outputtss')
        print tssfiles
        sDate = getStartTimefromRuninfo(runinfofile)
        tssFile = case + "/run_default/run.tss"
        logger.debug("Creating xml from tss: " + tssFile + "==> " + tssFile + ".xml")
        tss_topixml(tssFile,tssFile + ".xml","wflow","run",sDate,timestepsecs)
        tssFile = case + "/run_default/lev.tss"
        logger.debug("Creating xml from tss: " + tssFile + "==> " + tssFile + ".xml")
        tss_topixml(tssFile,tssFile + ".xml","wflow","lev",sDate,timestepsecs)
        for aa in tssfiles:
            tssFile = case + "/run_default/" + config.get("outputtss",aa) + ".tss"
            logger.debug("Creating xml from tss: " + tssFile + "==> " + tssFile + ".xml")
            tss_topixml(tssFile,tssFile + ".xml","wflow",config.get("outputtss",aa),sDate,timestepsecs)

        logger.info("Ending postadapter")
    else:
        sys.exit(2)

    # ...
if __name__ == "__main__":
    main()
