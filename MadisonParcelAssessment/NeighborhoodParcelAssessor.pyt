
# Import modules and packages
from io import BytesIO
from urllib.request import urlopen
from zipfile import ZipFile
import os
import tempfile
import shutil
import arcpy
from arcpy import env
from arcpy import da



class Toolbox(object):

    def __init__(self):
        """
        This tool box contains one tool, called DevelopmentParcelEvaluator.  The tool functions by downloading
        5 shapefiles from https://data-cityofmadison.opendata.arcgis.com/ and manipulating them to give an
        output of two feature classes that may be used to assess parcels for residential development.
        """
        self.label = "NeighborhoodDevelopmentParcelAssessorToolbox"
        self.alias = "Neighborhood_Redevelopment_Assessor_by_parcel"

        # List of tool classes associated with this toolbox
        self.tools = [Tool]


class Tool(object):
    """
    This tool returns two geodatabases to the file directory specified in parameter 1. One contains
    all the layers manipulated within this tool and the other contains only the resulting two layers of interest.
    This tool also returns a log in the form of a text file to the file directory specified.
    """
    def __init__(self):

        self.label = "ResidentialParcelDevelopmentEvaluator"
        self.description = "Tool to join parcel information to neighborhood redevelopment plots and" \
                           " assess them for redevelopment"
        self.canRunInBackground = False

    def getParameterInfo(self):
        """:param parameters:
        param1: Local File folder- specify the directory in which data is to be downloaded and manipulated
        The following two parameters specify the distance from parks and bus stops respectively within which a user
        has interest in residential parcels to be redeveloped
        param2: Distance from Park (miles)-default value is 0.25
        param3: Distance from Bus Stop (feet)-default value is 1320 feet (equivalent of 0.25 miles)
        parameter4: Park weight-weight of the specified distance to parks in index calculation. (default is 1)
        parameter5: Bus weight-weight of the distance to metro stop in index field calculation. (default is 1)
        parameter6: vacant weight-weight of a vacant lot in calculating index. (default is 1)

        """

        parameter0 = arcpy.Parameter(
            displayName="Local File Folder",
            name="in_workspace",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input")

        parameter1 = arcpy.Parameter(
            displayName="Distance From Park (Miles)",
            name="park_distance",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input",)
        parameter1.value = 0.25


        parameter2 = arcpy.Parameter(
            displayName="Distance From Bus Stop (Feet)",
            name="bus_stop_distance",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input",)
        parameter2.value = 1320
        parameter2.filter.type = "Range"
        parameter2.filter.list = [1, 1000000]

        parameter3 = arcpy.Parameter(
            displayName="Park Distance Weight",
            name="park_weight",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input",
            category="Investment Weights")
        parameter3.value = 1.0

        parameter4 = arcpy.Parameter(
            displayName="Bus Distance Weight",
            name="bus_weight",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input",
            category="Investment Weights")
        parameter4.value = 1.0

        parameter5 = arcpy.Parameter(
            displayName="Vacant Lot Weight",
            name="vacant_weight",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input",
            category="Investment Weights")
        parameter5.value = 1.0

        parameters = [parameter0, parameter1, parameter2, parameter3, parameter4, parameter5]
        return parameters

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def execute(self, parameters, messages):
        """

        :param parameters:
        parameter1: Local File folder- specify the directory in which data is to be downloaded and manipulated
        The following two parameters specify the distance from parks and bus stops respectively within which a user
        has interest in residential parcels to be redeveloped
        parameter2: Distance from Park (miles)
        parameter3: Distance from Bus Stop (feet)
        The following parameters are the relative weights of the three fields used in the calculation of the
        investment index field.  They will default to 1.
        parameter4: Park weight-weight of the specified distance to parks in index calculation
        parameter5: Bus weight-weight of the distance to metro stop in index field calculation
        parameter6: vacant weight-weight of a vacant lot in calculating index.

        :return: This tool returns two geodatabases to the file directory specified in parameter 1. One contains
         all the layers manipulated within this tool and the other contains only the resulting two layers of interest.
         The layers returned in the 'Results' geodatabase contain a feature class for all the residential redevelopment
         plots with flag values for distance specified from parks and buses, and a flag for vacant lots. There is also
         a field for the sum of all three flags. The 2nd feature class returned is an interpolated diffusion surface
          of the estimated value assessment for all residential parcels in Madison.
        """
        arcpy.env.overwriteOutput = True

        # Custom function to download data from web to shapefile
        def download_shapefile(urlzip, dir):
            """
            function to download a zip file of spatial data from the web and convert to a shapefile in a local directory
            :param urlzip: the url of a .zip of spatial data (a shapefile)
            :param dir: a local directory
            :return shapefile located in dir, derived from urlzip:
            """
            tempdir = tempfile.mkdtemp()
            resp = urlopen(urlzip)
            z = ZipFile(BytesIO(resp.read()))
            z.extractall(tempdir)
            shapefile = [file for file in os.listdir(tempdir) if file.endswith('.shp') is True][0]
            files = os.listdir(tempdir)
            for f in files:
                shutil.move(tempdir + '/' + f, dir)
            shutil.rmtree(tempdir)

            return dir + '/' + shapefile

        path = parameters[0].valueAsText
        gdb = arcpy.CreateFileGDB_management(path, 'working_archive.gdb')[0]
        env.workspace = gdb

        # Download data
        Neighborhood_Development_Areas = 'https://opendata.arcgis.com/datasets/a9873b85ba184f0293e6941b349cf36e_9.zip'
        Tax_Assessment_Parcels = 'https://opendata.arcgis.com/datasets/0338b0638e4749c395f8d38b39a5c466_7.zip'
        Urban_Boundary = 'https://opendata.arcgis.com/datasets/07b6322754064046b38140b03f881ad2_22.zip'
        Parks = 'https://opendata.arcgis.com/datasets/9e00ff81868e49b7ba65d4e628b9e14f_6.zip'
        Metro_Bus_Stops = 'https://opendata.arcgis.com/datasets/58d6ef381b594afbb06862dc51480aa1_3.zip'
        devs = arcpy.Project_management(
                                        download_shapefile(Neighborhood_Development_Areas, gdb),
                                        'devs_projected',
                                        arcpy.SpatialReference(2287))
        parcs = arcpy.Project_management(
                                        download_shapefile(Tax_Assessment_Parcels, gdb),
                                        'parcels_projected',
                                        arcpy.SpatialReference(2287))

        madison = arcpy.Project_management(
                                        download_shapefile(Urban_Boundary, gdb),
                                        'madison_projected',
                                        arcpy.SpatialReference(2287))
        parks = arcpy.Project_management(
                                        download_shapefile(Parks, gdb),
                                        'parks_projected',
                                        arcpy.SpatialReference(2287))
        bus = arcpy.Project_management(
                                        download_shapefile(Metro_Bus_Stops, gdb),
                                        'buses_projected',
                                        arcpy.SpatialReference(2287))

        #assign variables
        prk_weight = parameters[3].value
        bus_weight = parameters[4].value
        vcnt_weight = parameters[5].value

        # Join neighborhood developments and parcels and buffer parks
        buff_parks = arcpy.Buffer_analysis(parks,
                                           'parks_buff',
                                           '{} Miles'.format(parameters[1].value),
                                           '', '', 'ALL')[0]
        parc_select = arcpy.SelectLayerByLocation_management(parcs, 'INTERSECT', devs)[0]
        parcels = arcpy.CopyFeatures_management(parc_select, 'select_parcs')[0]
        dev_select = arcpy.SelectLayerByLocation_management(devs, 'INTERSECT', parcels)[0]
        devels = arcpy.CopyFeatures_management(dev_select, 'select_devs')[0]

        # Add all neighborhood development fields and add specified parcel layers to new fc
        fms = arcpy.FieldMappings()
        fms.addTable(devs)
        p_fields = ['CurrentTot', 'PropertyUs', 'PropertyCl']
        for field in p_fields:
            x = arcpy.FieldMap()
            x.addInputField(parcs, field)
            fms.addFieldMap(x)
        dev_parcs = arcpy.SpatialJoin_analysis(devels, parcels, 'Residential_Development_Parcels', '', '', fms)[0]

        # Begin analysis
        # Breate flag variables for distance to parks and buses, and if lot is vacant
        a_fs = ['Park_flag', 'Bus_flag', 'Vacant_flag']
        for field in a_fs:
            arcpy.AddField_management(dev_parcs, field, 'LONG')
        selection1 = arcpy.SelectLayerByLocation_management(dev_parcs, 'INTERSECT', buff_parks)[0]
        arcpy.CalculateField_management(selection1, 'Park_flag', 1)
        arcpy.SelectLayerByAttribute_management(dev_parcs, 'CLEAR_SELECTION')
        arcpy.Near_analysis(dev_parcs, bus)
        arcpy.AddField_management(dev_parcs, 'Invest_Index', 'FLOAT')

        with da.UpdateCursor(dev_parcs, ['PropertyCl']) as ucur:
            for row in ucur:
                if row[0] != 'Residential':
                    ucur.deleteRow()

        # Assign values to flag fields
        with da.UpdateCursor(dev_parcs,
                             ['Bus_flag', 'NEAR_DIST', 'Vacant_flag', 'PropertyUs', 'Park_flag', 'Invest_Index']
                             ) as ucur:
            for row in ucur:
                if row[1] <= parameters[2].value:
                    row[0] = 1
                else:
                    row[0] = 0
                if row[3] == 'Vacant':
                    row[2] = 1
                else:
                    row[2] = 0
                if row[4] != 1:
                    row[4] = 0
                row[5] = row[0]*bus_weight + row[2]*vcnt_weight + row[4]*prk_weight

                ucur.updateRow(row)

        # create gdb of results only
        gdb_final = arcpy.CreateFileGDB_management(path, 'Results.gdb')[0]
        env.workspace = gdb_final
        with da.UpdateCursor(parcs, ['PropertyCl']) as ucur:
            for row in ucur:
                if row[0] != 'Residential':
                    ucur.deleteRow()

        # Create diffusion map of residential parcel values
        diffusion_map = arcpy.DiffusionInterpolationWithBarriers_ga(parcs,
                                                                    'CurrentTot',
                                                                    'Interp_Results',
                                                                    'Residential_Parcel_Value_Diffusion_Map',
                                                                    '', madison)[0]
        # Copy residential layer for redevelopment to Results.gdb
        new_dev_parcs = arcpy.CopyFeatures_management(dev_parcs,
                                                      '{}\Residential_Development_Parcels'.format(gdb_final))

        return diffusion_map, new_dev_parcs


