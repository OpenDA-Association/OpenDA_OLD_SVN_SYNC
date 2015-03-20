﻿using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using OpenDA.DotNet.Interfaces;
using OpenDA.DotNet.OpenMI.Bridge;
using org.openda.application;
using java.io;
using MikeSheInOpenDA;
using System.IO;

namespace startRun
{
    class Program
    {
        static void Main(string[] args)
        {
            System.Console.WriteLine(Directory.GetCurrentDirectory());
            string mikeSheConfigFile = "";
            string odaDirectoryPath = "";
            string odaFileName = "";
            // Args Requires 2 fields:
            // 1) the MikeSHEConfig.txt
            // 2) the .oda file
            if (args[0] != null && args[1] != null)
            {

                
                // CHECK if files exist using Relative Paths.
                string currentDirectory = System.IO.Directory.GetCurrentDirectory();
                

                string arg1 = currentDirectory + args[0];
                string arg2 = currentDirectory + args[1];

                Uri uri1 = new Uri(Path.Combine(currentDirectory, arg1));
                Uri uri2 = new Uri(Path.Combine(currentDirectory, arg2));


                string file1 = Path.GetFullPath(uri1.AbsolutePath);
                string file2 = Path.GetFullPath(uri2.AbsolutePath);

                // IF RELATIVE PATHS
                if (System.IO.File.Exists(file1) && System.IO.File.Exists(file2))
                {

                    mikeSheConfigFile = file1;
                    odaFileName = System.IO.Path.GetFileName(file2);
                    odaDirectoryPath = System.IO.Path.GetDirectoryName(file2);
                }
                    // ELSE IF ABSOLUTE PATHS
                else if (System.IO.File.Exists(args[0]) && System.IO.File.Exists(args[2]))
                {
                    mikeSheConfigFile = args[0];
                    odaFileName = System.IO.Path.GetFileName(args[1]);
                    odaDirectoryPath = System.IO.Path.GetDirectoryName(args[1]);
                }
                else
                {
                    throw new System.IO.FileNotFoundException(" One or more of the files were not found \n" + args[0] +
                                                              "\n" + args[1]);
                }
            }
            else
            {
                // Args Requires 2 fields:
                // 1) the MikeSHEConfig.txt
                // 2) the .oda file
                System.Console.WriteLine("Takes two args 1) the mikeSHEConfig.txt   and   2) the OpenDA  .oda file.\n"  );
            }


            MikeSheOpenMIModelFactory mikeSheOpenMIModelFactory = new MikeSheOpenMIModelFactory();
            mikeSheOpenMIModelFactory.Initialize(Path.GetDirectoryName(mikeSheConfigFile), new[] { Path.GetFileName(mikeSheConfigFile) });

            OpenDA.DotNet.OpenMI.Bridge.ModelFactory.InsertModelFactory(mikeSheOpenMIModelFactory);

            ModelFactory openDaModelFactory = new ModelFactory();
            openDaModelFactory.Initialize(null, null);

            ApplicationRunnerSingleThreaded applicationRunner = new ApplicationRunnerSingleThreaded();


            applicationRunner.runSingleThreaded(new java.io.File(odaDirectoryPath), odaFileName);

            System.Console.WriteLine("Done. Hit a key!");
            System.Console.ReadKey();
        }
    }
}
