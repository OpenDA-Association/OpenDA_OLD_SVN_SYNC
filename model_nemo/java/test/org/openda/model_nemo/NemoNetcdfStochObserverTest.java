package org.openda.model_nemo;

import junit.framework.TestCase;
import org.openda.interfaces.IStochObserver;
import org.openda.interfaces.ITime;
import org.openda.interfaces.IVector;
import org.openda.utils.OpenDaTestSupport;
import org.openda.utils.Time;

import java.io.File;
import java.io.IOException;

/**
 * Created by nils on 12/05/14.
 */
public class NemoNetcdfStochObserverTest extends TestCase {

	OpenDaTestSupport testData = null;
	private File testRunDataDir;
	private File testCopyDir;


	protected void setUp() throws IOException {
		testData = new OpenDaTestSupport(NemoWrapperTest.class, "model_nemo");
		testRunDataDir = testData.getTestRunDataDir();
		testCopyDir = new File(testRunDataDir,"copy");
	}

	public void testAllDates(){
		IStochObserver observer = new NemoNetcdfStochObserver();
		String args[] = {};
		observer.initialize(testRunDataDir, args);

		/* Note: this method is not implemented correctly
		         when selecting multiple days it will return all possible
		         different days but not the time of each and every observations
		 */
		ITime times[]=observer.getTimes();
		assertEquals("Checking different dates:",times.length,3);
		assertEquals(times[0].getMJD(), 55993, 0.001);
		assertEquals(times[1].getMJD(), 56000, 0.001);
		assertEquals(times[2].getMJD(), 56007, 0.001);

	};

	public void testDateSelection(){

		IStochObserver observer = new NemoNetcdfStochObserver();
		String args[] = {};
		observer.initialize(testRunDataDir, args);
		Time selection = new Time(56000);
		IStochObserver subObs=observer.createSelection(selection);
		ITime times[]=subObs.getTimes();
		assertEquals("Checking date:",times.length,4413);
		assertEquals(times[100].getMJD(), 56000, 0.001);
		assertEquals(times[4412].getMJD(), 56000, 0.001);
	}

	public void testGetValues(){

		IStochObserver observer = new NemoNetcdfStochObserver();
		String args[] = {};
		observer.initialize(testRunDataDir, args);
		Time selection = new Time(56000);
		IStochObserver subObs=observer.createSelection(selection);
		ITime times[]=subObs.getTimes();
		assertEquals("Checking date:",times.length,4413);
		assertEquals(times[100].getMJD(), 56000, 0.001);
		assertEquals(times[4412].getMJD(), 56000, 0.001);

		IVector values = subObs.getValues();
		double norm=values.norm2();
		assertEquals("Checking number of measurements", 4413,values.getSize());
		assertEquals("Checking norm of vector with measured values", 6708197.225,norm, 0.001);



	}





}
