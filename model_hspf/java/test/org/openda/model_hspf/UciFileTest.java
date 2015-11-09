/* MOD_V2.0
 * Copyright (c) 2012 OpenDA Association
 * All rights reserved.
 *
 * This file is part of OpenDA.
 *
 * OpenDA is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as
 * published by the Free Software Foundation, either version 3 of
 * the License, or (at your option) any later version.
 *
 * OpenDA is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with OpenDA.  If not, see <http://www.gnu.org/licenses/>.
 */

package org.openda.model_hspf;

import junit.framework.TestCase;
import org.openda.exchange.timeseries.TimeUtils;
import org.openda.interfaces.IExchangeItem;
import org.openda.interfaces.IPrevExchangeItem;
import org.openda.utils.OpenDaTestSupport;
import org.openda.utils.Time;
import org.openda.utils.io.AsciiFileUtils;

import java.io.File;
import java.io.IOException;
import java.util.Calendar;
import java.util.TimeZone;

/**
 * Test class for testing UciIoObject and UciExchangeItem.
 *
 * @author Arno Kockx
 */
public class UciFileTest extends TestCase {

    private OpenDaTestSupport testData;
    private File testRunDataDir;

    protected void setUp() throws IOException {
    	testData = new OpenDaTestSupport(UciFileTest.class, "model_hspf");
        testRunDataDir = testData.getTestRunDataDir();
    }

    public void testWriteUciFile() {
        Calendar calendar = Calendar.getInstance();
        calendar.setTimeZone(TimeUtils.createTimeZoneFromDouble(9));
        calendar.set(2005, 0, 1, 0, 0, 0);
        calendar.set(Calendar.MILLISECOND, 0);
        double startDate = Time.milliesToMjd(calendar.getTimeInMillis());
        calendar.set(2007, 0, 1, 0, 0, 0);
        calendar.set(Calendar.MILLISECOND, 0);
        double stopDate = Time.milliesToMjd(calendar.getTimeInMillis());

        UciIoObject uciIoObject = new UciIoObject();
        String uciFilename = "uciFileTest/input/ndriver.uci";
        String[] arguments = new String[]{"9", "TSTART", "TSTOP"};
        uciIoObject.initialize(testRunDataDir, uciFilename, arguments);

        //Get all exchangeItems items
        IPrevExchangeItem[] exchangeItems = uciIoObject.getExchangeItems();
        assertEquals(2, exchangeItems.length);

        //Loop over all exchangeItems items and request the ID, name and value
        for (IPrevExchangeItem exchangeItem : exchangeItems) {
            String id = exchangeItem.getId();
            if ("TSTART".equals(id)) {
                exchangeItem.setValues(startDate);
            } else if ("TSTOP".equals(id)) {
                exchangeItem.setValues(stopDate);
            }
        }

        //This command actually replaces the tags in the uci file by the values
        //of the corresponding exchangeItems.
        uciIoObject.finish();

        //compare actual result file with expected result file.
        File actualOutputFile = new File(testRunDataDir, uciFilename);
        File expectedOutputFile = new File(testRunDataDir, "uciFileTest/expectedResult/ndriver_expected.uci");
        assertTrue(testData.FilesAreIdentical(expectedOutputFile, actualOutputFile, 0));
    }

    public void testWriteUciFileWithExtendedPeriod() {
        Calendar calendar = Calendar.getInstance();
        calendar.setTimeZone(TimeZone.getTimeZone("GMT"));

        calendar.set(2007, 0, 1, 0, 0, 0);
        calendar.set(Calendar.MILLISECOND, 0);
        double startDate = Time.milliesToMjd(calendar.getTimeInMillis());
        calendar.set(2007, 0, 5, 9, 0, 0);
        calendar.set(Calendar.MILLISECOND, 0);
        double stopDate = Time.milliesToMjd(calendar.getTimeInMillis());

        UciIoObject uciIoObject = new UciIoObject();
        String uciFilename = "uciFileTest/input/ndriver_extended_period.uci";
        String[] arguments = new String[]{"0", "TSTART", "TSTOP", "-43800"};
        uciIoObject.initialize(testRunDataDir, uciFilename, arguments);

        //Get all exchangeItems items
        IPrevExchangeItem[] exchangeItems = uciIoObject.getExchangeItems();
        assertEquals(2, exchangeItems.length);

        //Loop over all exchangeItems items and request the ID, name and value
        for (IPrevExchangeItem exchangeItem : exchangeItems) {
            String id = exchangeItem.getId();
            if ("TSTART".equals(id)) {
                exchangeItem.setValues(startDate);
            } else if ("TSTOP".equals(id)) {
                exchangeItem.setValues(stopDate);
            }
        }

        //This command actually replaces the tags in the uci file by the values
        //of the corresponding exchangeItems.
        uciIoObject.finish();

        //compare actual result file with expected result file.
        File actualOutputFile = new File(testRunDataDir, uciFilename);
        File expectedOutputFile = new File(testRunDataDir, "uciFileTest/expectedResult/ndriver_extended_period_expected.uci");
        assertTrue(testData.FilesAreIdentical(expectedOutputFile, actualOutputFile, 0));
    }

	public void testWriteUciFileWithoutTags() {
		Calendar calendar = Calendar.getInstance();
		calendar.setTimeZone(TimeUtils.createTimeZoneFromDouble(9));
		calendar.set(2005, 0, 1, 0, 0, 0);
		calendar.set(Calendar.MILLISECOND, 0);
		double startDate = Time.milliesToMjd(calendar.getTimeInMillis());
		calendar.set(2007, 0, 1, 0, 0, 0);
		calendar.set(Calendar.MILLISECOND, 0);
		double endDate = Time.milliesToMjd(calendar.getTimeInMillis());

		UciDataObject uciDataObject = new UciDataObject();
		String uciFilename = "uciFileTest/input/ndriver_without_tags.uci";
		String[] arguments = new String[]{uciFilename, "9", "TSTART", "TSTOP"};
		uciDataObject.initialize(testRunDataDir, arguments);

		String[] exchangeItemIds = uciDataObject.getExchangeItemIDs();
		assertEquals(2, exchangeItemIds.length);

		//set start and end time in exchangeItems.
		IExchangeItem startTimeExchangeItem = uciDataObject.getDataObjectExchangeItem("TSTART");
		assertNotNull(startTimeExchangeItem);
		startTimeExchangeItem.setValues(startDate);
		IExchangeItem endTimeExchangeItem = uciDataObject.getDataObjectExchangeItem("TSTOP");
		assertNotNull(endTimeExchangeItem);
		endTimeExchangeItem.setValues(endDate);

		//the call to method finish actually writes the data in the exchangeItems to the uci file.
		uciDataObject.finish();

		File actualOutputFile = new File(testRunDataDir, uciFilename);
		File expectedOutputFile = new File(testRunDataDir, "uciFileTest/expectedResult/ndriver_without_tags_expected.uci");
		assertEquals("Actual output file '" + actualOutputFile + "' does not equal expected output file '" + expectedOutputFile + "'.",
				AsciiFileUtils.readText(expectedOutputFile), AsciiFileUtils.readText(actualOutputFile));
	}

    public void testReadUciStateFile() {
        UciStateDataObject uciStateDataObject = new UciStateDataObject();
        String uciFilename = "uciFileTest/input/ndriver_state_file.uci";
        String[] arguments = new String[]{uciFilename};
        uciStateDataObject.initialize(testRunDataDir, arguments);

        String[] exchangeItemIds = uciStateDataObject.getExchangeItemIDs();
        assertEquals(3944, exchangeItemIds.length);

        //HEAT-INIT
        IExchangeItem item = uciStateDataObject.getDataObjectExchangeItem("1.AIRTMP");
        assertNotNull(item);
        assertEquals(34d, item.getValues());
        item = uciStateDataObject.getDataObjectExchangeItem("42.AIRTMP");
        assertNotNull(item);
        assertEquals(34d, item.getValues());
        item = uciStateDataObject.getDataObjectExchangeItem("232.AIRTMP");
        assertNotNull(item);
        assertEquals(34d, item.getValues());
        item = uciStateDataObject.getDataObjectExchangeItem("233.AIRTMP");
        assertNull(item);

        //HYDR-INIT
        item = uciStateDataObject.getDataObjectExchangeItem("56.VOL");
        assertNotNull(item);
        assertEquals(100d, item.getValues());
        item = uciStateDataObject.getDataObjectExchangeItem("57.VOL");
        assertNotNull(item);
        assertEquals(400000d, item.getValues());
        item = uciStateDataObject.getDataObjectExchangeItem("58.VOL");
        assertNotNull(item);
        assertEquals(100d, item.getValues());
    }

    public void testWriteUciStateFile() {
        UciStateDataObject uciStateDataObject = new UciStateDataObject();
        String uciFilename = "uciFileTest/input/ndriver_state_file.uci";
        String[] arguments = new String[]{uciFilename};
        uciStateDataObject.initialize(testRunDataDir, arguments);

        //set values in exchangeItems.
        //HEAT-INIT
        IExchangeItem item = uciStateDataObject.getDataObjectExchangeItem("1.AIRTMP");
        assertNotNull(item);
        item.setValues(-1d);
        item = uciStateDataObject.getDataObjectExchangeItem("42.AIRTMP");
        assertNotNull(item);
        item.setValues(42d);
        item = uciStateDataObject.getDataObjectExchangeItem("232.AIRTMP");
        assertNotNull(item);
        item.setValues(1000d);

        //HYDR-INIT
        item = uciStateDataObject.getDataObjectExchangeItem("56.VOL");
        assertNotNull(item);
        item.setValues(0.56d);
        item = uciStateDataObject.getDataObjectExchangeItem("57.VOL");
        assertNotNull(item);
        item.setValues(0.57d);
        item = uciStateDataObject.getDataObjectExchangeItem("58.VOL");
        assertNotNull(item);
        item.setValues(0.58d);

        //the call to method finish actually writes the data in the exchangeItems to the uci file.
        uciStateDataObject.finish();

        File actualOutputFile = new File(testRunDataDir, uciFilename);
        File expectedOutputFile = new File(testRunDataDir, "uciFileTest/expectedResult/ndriver_state_file_expected.uci");
        assertEquals("Actual output file '" + actualOutputFile + "' does not equal expected output file '" + expectedOutputFile + "'.",
                AsciiFileUtils.readText(expectedOutputFile), AsciiFileUtils.readText(actualOutputFile));
    }
}
