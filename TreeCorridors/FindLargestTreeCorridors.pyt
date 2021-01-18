# -*- coding: utf-8 -*-

# The following arcpy Toolbox was developed in response to a question on a midterm as part of an MS in GIS
# Course. The Question it is in response to is reproduced below:
#
# Build a Python Toolbox that follows the Python standards taught so far with documentation, logging,
# etc.. The tool must perform a minimum of 3 spatial operations and write new output out to a user.
# The intermediate data should be written to a temporary directory and be cleaned up after every use.
# Additionally, have at least 1 choice list of strings for the input and at least 1 output.

from io import BytesIO
from urllib.request import urlopen
from zipfile import ZipFile
import logging
import os
import shutil
import tempfile
import arcpy


class Toolbox(object):
    def __init__(self):
        """
        This toolbox contains a single tool that calculates tree corridors in Boston. This tool is described in greater
        detail below.
        """
        self.label = "BostonTreeCorridorCalculator"
        self.alias = "BostonTreeCorridorCalculator "

        # List of tool classes associated with this toolbox
        self.tools = [Tool]


class Tool(object):
    def __init__(self):
        """
        This tool uses planimetric data of Trees in the city of Boston to generate tree corridors based on a specified
        distance between trees, and a desired number of larger corridors.  This data may be used in identifying
        suitable habitat for certain kinds of birds who thrive while being able to travel a certain minimum distance
        from tree to tree.  Alternatively, this tool may be used to simply identify those areas in Boston with a higher
        density of trees than neighboring areas.  This tool identifies the N largest corridors of specified distance
        within Boston. Tree data can be found here: https://data.boston.gov/dataset/trees.

        In addition to buffering and dissolving the tree layer, this tool adds a field to the output feature class
        called 'P_AREA' that indicates the percent of the total area of the tree area defined by the buffered tree
        layer.  Thus it is a rough representation of the total tree cover in the city (or of that specific tree type
        if a type is specified.

        This tool also creates a log record in the same folder as the output (or one layer above if output is set to be
        in a geodatabase). For ease of recognition, this log is stored as 'TreeCorridorLog.log'.

        The downloadig of this data and spatial operations defined above may take a bit of tie to process depending on
        the operating system.
        """
        self.label = "DefineLargestTreeCorridors"
        self.description = "Tool to identify largest tree corridors in Boston"
        self.canRunInBackground = False

    def getParameterInfo(self):
        """
        :param out_fc: The name and location of the output feature class.
        :param buff_dist: The distance in feet from which to define the criteria for the corridor
        :param num: an integer specifying the number of desired output corridor features. The 'num' largest areas
            are selected for inclusion.
        :param tree_type: Each tree in the above dataset is characterized as a 'PARK-TREE', or a 'STREET-TREE'. 
            Specifying one of these types from the list will limit the corridors to this tree type. This is an
            optional parameter and the default does not differentiate between these tree types. NOTE: These field
            names have changed over time and if the specified output is not working, consult the planimetric tree data
            for updated field names.
            """

        parameter0 = arcpy.Parameter(
            displayName="Output Feature Class:",
            name="out_fc",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Output")
        parameter0.value = 'TreeCorridors'

        parameter1 = arcpy.Parameter(
            displayName="Required Tree Density (in Feet):",
            name="buff_dist",
            datatype="GPLong",
            parameterType="Required",
            direction="Input")
        parameter1.filter.type = "Range"
        parameter1.filter.list = [1, 1000]

        parameter2 = arcpy.Parameter(
            displayName="Number of Largest Tree Corridors Desired:",
            name="num",
            datatype="GPLong",
            parameterType="Required",
            direction="Input")
        parameter2.filter.type = "Range"
        parameter2.filter.list = [1, 1000]

        parameter3 = arcpy.Parameter(
            displayName="Tree Type in Output: (Optional)",
            name="tree_type",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")
        parameter3.filter.list = ['PARK-TREE', 'STREET-TREE']

        params = [parameter0, parameter1, parameter2, parameter3]
        return params

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def execute(self, parameters, messages):
        """
        :param parameters: defined above in parameters
        :param messages:
        :return: This tool creates a single output feature class as a shapefile or geodatabse feature class as
            defined by the user. The feature class will contain N records equal to the integer parameter 'num'.
            These records represent the N largest tree corridors that allow for X distance between trees as defined
            by the buff-dist parameter.
        """

        def download_shapefile(urlzip, dir):
            """
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

        def top_field_values(fc, field, num):
            """
            :param fc: A Feature class of spatial data (shapefile or geodatabase feature class)
            :param field: A string value representing a field of numeric data within the feature class
            :param num: An integer that determines the number of highest values of the param field o return
            :return: returns N=num of the highest values of the defined field as a list
            """

            values = []
            with arcpy.da.SearchCursor(fc, field) as scur:
                for row in scur:
                    values.append(row[0])
            top_values = sorted(values)
            return top_values[-num:]

        def sum_field_values(fc, field):
            """
            :param fc: A Feature class of spatial data (shapefile or geodatabase feature class)
            :param field: A string value representing a field of numeric data within the feature class
            :return: the sum of the values of all the fc field attributes as a single float
            """

            values = []
            with arcpy.da.SearchCursor(fc, field) as scur:
                for row in scur:
                    values.append(row[0])
            return sum(values)

        output_fc = parameters[0].valueAsText
        dist = parameters[1].value
        num = parameters[2].value
        input_field = parameters[3].valueAsText
        path = os.path.split(output_fc)[0]
        if path.endswith('.gdb'):
            path = os.path.split(path)[0]

        logging.basicConfig(
                filename=f'{path}/TreeCorridorLog.log',
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%m-%d-%Y : %H:%M:%S')

        try:

            tempdir = tempfile.mkdtemp()
            logging.info(f'Temp directory: {tempdir}')
            boston_trees = \
                'http://bostonopendata-boston.opendata.arcgis.com/datasets/ce863d38db284efe83555caf8a832e2a_1.zip'
            trees = arcpy.Project_management(download_shapefile(boston_trees, tempdir),
                                             f'{tempdir}/trees_projected.shp',
                                             arcpy.SpatialReference(2249))

            # First spatial operation: buffer tree point layer desired distance
            if input_field is not None:
                sql_clause = f"TYPE = '{input_field}'"
                logging.info(f'Selecting {input_field} features from {trees}. . .')
                select = arcpy.SelectLayerByAttribute_management(trees, 'NEW_SELECTION', sql_clause)
                logging.info(f'Buffering {select} {dist} Feet. . .')
                buf = arcpy.Buffer_analysis(select, f'{tempdir}/trees_buf', f'{dist} Feet')[0]
                clear = arcpy.SelectLayerByAttribute_management(trees, 'CLEAR_SELECTION')
                del select
                del clear
            else:
                logging.info(f'Buffering {trees} {dist} Feet. . .')
                buf = arcpy.Buffer_analysis(trees, f'{tempdir}/trees_buf', f'{dist} Feet')[0]

            # delete original tree data
            logging.info(f'Deleting {trees}. . .')
            arcpy.Delete_management(trees)

            # Second spatial operation: dissolve boundaries of buffered feature class
            logging.info(f'Dissolving {buf} boundaries . . .')
            arcpy.AddMessage(f'Dissolving {buf} boundaries . . .')
            if input_field is not None:
                fc = arcpy.DissolveBoundaries_gapro(buf, output_fc, '', 'DISSOLVE_FIELDS', 'TYPE')[0]
            else:
                fc = arcpy.DissolveBoundaries_gapro(buf, output_fc)[0]
            if fc.endswith('.shp'):
                arcpy.AddField_management(fc, 'SHAPE_Area', 'FLOAT')
                arcpy.CalculateGeometryAttributes_management(fc, [['SHAPE_Area', 'AREA']])

            # Third spatial operation: calculate percent \
            # of city tree cover of its type represented for each tree cover polygon
            tot_area = sum_field_values(fc, 'SHAPE_Area')
            arcpy.AddField_management(fc, 'P_AREA', 'FLOAT')
            logging.info(f'Calculating percent of total area of {input_field} for each feature in {fc}. . .')
            arcpy.CalculateField_management(fc, 'P_AREA', f'round(!SHAPE_Area!/ {tot_area}*100, 2)')

            # Select desired number of records for final feature class
            logging.info(f'Identifying largest {num} tree cover areas. . .')
            top_areas = top_field_values(fc, 'SHAPE_Area', num)
            with arcpy.da.UpdateCursor(fc, ['SHAPE_Area', 'OID@']) as ucur:
                for row in ucur:
                    if row[0] not in top_areas:
                        ucur.deleteRow()

            # Delete temporary workspace with intermediate data
            shutil.rmtree(tempdir)
            logging.info(f'{tempdir} successfully deleted')

        except arcpy.ExecuteError as ae:
            logging.error(f'ERROR: {ae}')

        except Exception as e:
            logging.error(f'ERROR:{e}')
        return
