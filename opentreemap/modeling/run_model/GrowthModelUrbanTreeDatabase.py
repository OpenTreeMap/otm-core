# -*- coding: utf-8 -*-
# flake8: noqa
from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division

from copy import deepcopy
from operator import itemgetter

from math import exp, log, sqrt

from treemap.models import Species
from treemap.species import species_for_otm_code


class GrowthModelUrbanTreeDatabase(object):

    reference = (
        'McPherson, E. Gregory; van Doorn, Natalie S.; Peper, Paula J. 2016. '
        'Urban tree database. Fort Collins, CO: Forest Service Research Data '
        'Archive. http://www.fs.usda.gov/rds/archive/Product/RDS-2016-0005')

    schema = None

    @classmethod
    def get_default_params(cls, instance):
        return deepcopy({
            'model_name': 'UrbanTreeDatabase',
            'version': 1,
            'params': {}
        })

    @classmethod
    def get_species_for_planting(cls, instance):
        return _get_species_for_planting(instance)

    def __init__(self, params, instance):
        # TODO: Handle instance with multiple i-Tree regions
        itree_regions = instance.itree_regions()
        if len(itree_regions) == 0:
            raise Exception("i-Tree region not specified")
        self._itree_region = itree_regions[0].code

    def init_tree(self, tree):
        (age_to_diameter, min_age, max_age) = \
            _growth_data[self._itree_region][tree.species.otm_code]

        min_diameter = age_to_diameter(min_age)
        max_diameter = age_to_diameter(max_age)
        growth_rate_at_min_age = age_to_diameter(min_age + 1) - min_diameter

        # Compute initial age from initial diameter
        if tree.diameter < min_diameter:
            # The tree diameter is too small to use the age_to_diameter function.
            # Instead, use the growth rate for the min_age year in a linear
            # interpolation to find the initial age.
            # (Note that Urban Tree Database age estimates are 0 at planting,
            # not germination, so a small initial diameter could return a
            # negative initial age.)
            tree.initial_age = \
                min_age - (min_diameter - tree.diameter) / growth_rate_at_min_age
        elif tree.diameter > max_diameter:
            raise Exception('Initial diameter %s above max %s for %s in %s' %
                            (tree.diameter, max_diameter,
                             tree.species.otm_code, self._itree_region))
        else:
            # Use bisection on the age_to_diameter function. We know that
            # age_to_diameter returns valid results for min_age and max_age,
            # and that age_to_diameter is monotonically increasing between
            # min_age and max_age.
            #
            # The largest difference between max_age and min_age is 192.
            # Using 16 iterations will guarantee the bisection completes to
            # a tolerance of .1 because 192 / 2**16 < .1
            tree.initial_age = bisect(
                age_to_diameter, min_age, max_age, tree.diameter, 16, .1)

        tree.age_to_diameter = age_to_diameter
        tree.min_age = min_age
        tree.max_age = max_age
        tree.growth_rate_at_min_age = growth_rate_at_min_age

    def grow_tree(self, tree, year):
        age = tree.initial_age + year
        if age < tree.min_age:
            growth = tree.growth_rate_at_min_age
        elif age > tree.max_age:
            growth = 0
        else:
            growth = tree.age_to_diameter(age) - tree.diameter
        tree.grow(growth)


def _get_species_for_planting(instance):
    # TODO: Handle instance with multiple i-Tree regions
    itree_regions = instance.itree_regions()

    if len(itree_regions) == 0:
        return []

    itree_region = itree_regions[0]
    otm_codes = _growth_data[itree_region.code].keys()
    species = [species_for_otm_code(otm_code) for otm_code in otm_codes]
    species = sorted(species, key=itemgetter('common_name'))

    def can_get_species(otm_code):
        return Species.get_by_code(instance, otm_code, itree_region.code) is not None
    species = [s for s in species if can_get_species(s['otm_code'])]

    return species


def bisect(f, x_lo, x_hi, y_target, max_iterations, tolerance):
    """
    Compute value of x for which f(x) is close to y_target
    :param f:  Function to be bisected
    :param x_lo:  x value for which f(x) < y_target
    :param x_hi:  x value for which f(x) > y_target
    :param y_target:  value of y for which x is desired
    :param max_iterations:  exception if iterations exceed this value
    :param tolerance:  ensure |f(x) - y_target| < tolerance
    :return:
    """
    if f(x_lo) > y_target or f(x_hi) < y_target:
        raise Exception("Bounds do not bracket target value")
    i = 1
    while i <= max_iterations:
        x_mid = (x_lo + x_hi) / 2.0
        if f(x_mid) == y_target or (x_hi - x_lo) / 2.0 < tolerance:
            return x_mid
        i += 1
        if f(x_mid) < y_target:
            x_lo = x_mid
        else:
            x_hi = x_mid
    raise Exception("Max iterations exceeded")



# Growth functions from TS4_Growth_eqn_forms.csv
# Note that 'mse' is 'mean-squared-error', which is listed in column 'c' of
# TS6_Growth_coefficients.csv

def loglogw1(a, b, mse):
    return lambda age: \
        exp(a + b * log(log(age + 1) + mse/2))

def loglogw2(a, b, mse):
    return lambda age: \
        exp(a + b * log(log(age + 1)) + sqrt(age) * mse/2)

def loglogw3(a, b, mse):
    return lambda age: \
        exp(a + b * log(log(age + 1)) + age * mse/2)

def loglogw4(a, b, mse):
    return lambda age: \
        exp(a + b * log(log(age + 1)) + age**2 * mse/2)

def lin(a, b):
    return lambda age: \
        a + b * age

def quad(a, b, c):
    return lambda age: \
        a + b * age + c * age**2

def cub(a, b, c, d):
    return lambda age: \
        a + b * age + c * age**2 + d * age**3

def expow1(a, b, mse):
    return lambda age: \
        exp(a + b * age + mse/2)

def expow2(a, b, mse):
    return lambda age: \
        exp(a + b * age + sqrt(age) * mse/2)

def expow3(a, b, mse):
    return lambda age: \
        exp(a + b * age + age * mse/2)

def expow4(a, b, mse):
    return lambda age: \
        exp(a + b * age + age**2 * mse/2)

# Growth data by region and species (OTM code) from TS6_Growth_coefficients.csv
#
# age_to_diameter - function to compute diameter given age
# min_age, max_age - from "Apps min" and "Apps max" columns
#  ("Reasonable minimum/maximum data value to use when applying this equation")
#
# Note: we have lowered max_age for 50 species below to ensure that the
# age_to_diameter function is monotonically increasing from min_age to max_age.

# Species codes converted to equivalent OTM codes:
# FREX_H -> FREXH  (Fraxinus excelsior 'Hessei')
# FRPE_M -> FRPEM  (Fraxinus pennsylvanica 'Marshall')
# FRVE_G -> FRVEG  (Fraxinus velutina 'Modesto')
# KOELFO -> KOEL   (Koelreuteria elegans)
# TACH   -> TACH4  (Tabebuia ochracea subsp. neochrysantha)

# Fixed these errors in the data:
# In SacVal, Fraxinus velutina listed as FRVE_G but should be FRVE
# In LoMidW, Pyrus calleryana 'Bradford' listed as PYCA but should be PYCA_B


_growth_data = {
    'CaNCCoJBK': {  # NoCalC
                 # age_to_diameter                                    min_age  max_age
        'ACME'  : (cub(2.85114, -0.12224, 0.05596, -0.0005),        2.78, 73.78), # max_age lowered             
        'ACPA'  : (cub(2.84767, 0.23083, 0.02511, -0.00028),        2.85, 47.39),                               
        'CICA'  : (quad(2.84131, 0.57502, 0.00312),                 2.84, 103.88),                              
        'EUGL'  : (quad(1.84032, 2.33198, -0.00865),                1.84, 134.84), # max_age lowered            
        'FRVE'  : (quad(2.84341, 0.65806, 0.00963),                 2.84, 84.4),                                
        'GIBI'  : (lin(2.07017, 0.63933),                           2.07, 39.15),                               
        'LIST'  : (quad(2.80359, 1.29151, -0.00299),                2.8, 102.01),                               
        'LITU'  : (lin(2.84107, 0.89367),                           2.84, 84.17),                               
        'MAGR'  : (quad(3.02259, 0.37655, 0.00889),                 3.02, 97.39),                               
        'PICH'  : (lin(2.81535, 0.75851),                           2.82, 36.95),                               
        'PIRA'  : (lin(2.80551, 1.60318),                           2.81, 115.03),                              
        'PIUN'  : (loglogw1(1.08072, 1.9017, 0.10108),              1.68, 52.08),                               
        'PLAC'  : (quad(2.83419, 1.1265, 0.00238),                  2.83, 102.17),                              
        'PRCE'  : (quad(2.84436, 0.56298, 0.00934),                 2.84, 54.36),                               
        'PYCA'  : (lin(0.55185, 1.13712),                           0.55, 57.41),                               
        'PYKA'  : (lin(2.83176, 1.30003),                           2.83, 67.83),                               
        'QUAG'  : (lin(1.55732, 1.48691),                           1.56, 150.25),                              
        'ROPS'  : (cub(2.84813, 0.18509, 0.07077, -0.00096),        2.85, 50.85), # max_age lowered             
        'SESE'  : (lin(2.79785, 1.99742),                           2.8, 154.6),                                
        'ULAM'  : (lin(2.3541, 1.40641),                            2.35, 121.9),                               
        'ULPA'  : (cub(2.85154, -0.15554, 0.07672, -0.00112),       2.84, 44.84), # max_age lowered             
    },                                                                                                         
    'CenFlaXXX': {  # CenFla                                                                                   
        'ACRU'  : (quad(-3.6811, 3.0548, -0.02326),                 2.34, 65.34), # max_age lowered             
        'CICA'  : (quad(-0.87708, 2.85059, -0.01321),               1.96, 107.96), # max_age lowered            
        'ERJA'  : (lin(1.72609, 1.77157),                           1.73, 54.87),                               
        'JUSI'  : (cub(-0.6109, 1.63311, 0.0145, -0.00022),         1.04, 76.04), # max_age lowered             
        'KOEL'  : (quad(1.54502, 2.71251, -0.02975),                1.55, 45.55), # max_age lowered             
        'LAIN'  : (lin(5.70526, 1.95628),                           5.71, 64.39),                               
        'LIST'  : (loglogw1(0.76105, 2.6362, 0.03839),              0.88, 99),                                  
        'MAGR'  : (quad(-1.74323, 2.41888, -0.01267),               3.04, 95.04), # max_age lowered             
        'PIEL'  : (loglogw1(0.23241, 3.06738, 0.12536),             2, 88.28),                                  
        'PLOC'  : (lin(-1.10175, 1.91487),                          2.73, 94.64),                               
        'PRCA'  : (quad(-2.76632, 3.70913, -0.04597),               0.9, 39.9), # max_age lowered               
        'QULA2' : (cub(1.30621, 1.23988, 0.04912, -0.00065),        1.31, 61.31), # max_age lowered             
        'QUSH'  : (quad(2.54333, 1.42769, 0.02543),                 2.54, 77.35),                               
        'QUVI'  : (cub(-7.62777, 3.34615, -0.03523, 0.00024),       2.1, 194.32),                               
        'THOR'  : (cub(-9.74097, 7.50867, -0.4091, 0.00767),        3.7, 54.3),                                 
        'TRSE6' : (lin(2.59625, 1.99853),                           2.6, 82.54),                                
        'ULPA'  : (loglogw3(0.493514813, 2.550671555, 0.004334238), 0.64, 76.97),                               
    },                                                                                                          
    'GulfCoCHS': {  # GulfCo                                                                                    
        'ACRU'  : (lin(2.52944, 1.78455),                           2.53, 70.34),                               
        'CAIL'  : (lin(2.52741, 1.25824),                           2.53, 90.6),                                
        'CELA'  : (cub(3.03874, 0.92424, 0.06529, -0.00125),        3.04, 41.04), # max_age lowered             
        'COFL'  : (loglogw1(0.96778, 1.85836, 0.08767),             1.49, 34.53),                               
        'GLTR'  : (quad(2.52626, 1.37056, -0.01467),                2.53, 34.54),                               
        'ILOP'  : (cub(2.53924, 0.07682, 0.08877, -0.00172),        2.54, 34.54), # max_age lowered             
        'JUVI'  : (quad(2.53228, 0.77567, 0.01293),                 2.53, 84.3),                                
        'LAIN'  : (lin(3.85142, 1.17328),                           3.85, 62.52),                               
        'LIST'  : (quad(2.60246, 2.35752, -0.01702),                2.6, 69.6), # max_age lowered               
        'MAGR'  : (lin(2.5468, 1.21823),                            2.55, 67.11),                               
        'PITA'  : (quad(2.50889, 1.77264, -0.00698),                2.51, 114.35),                              
        'PLOC'  : (lin(2.52516, 1.48428),                           2.53, 115.33),                              
        'PYCA'  : (lin(2.52382, 1.61683),                           2.52, 67.2),                                
        'QULA2' : (quad(2.10784, 1.84871, -0.0057),                 2.11, 115.35),                              
        'QUNI'  : (cub(2.53058, 0.94546, 0.0262, -0.00032),         2.53, 68.53), # max_age lowered             
        'QUPH'  : (lin(2.52535, 1.46083),                           2.53, 115.01),                              
        'QUVI'  : (quad(0.94464, 2.24738, -0.01091),                0.94, 102.94), # max_age lowered            
    },                                                                                                          
    'InlEmpCLM': {  # InlEmp                                                                                    
        'BRPO'  : (cub(1.67923, 2.25021, -0.08017, 0.00122),        1.68, 66.02),                               
        'CICA'  : (cub(2.27682, 2.12158, -0.02701, 0.00016),        2.28, 160.68),                              
        'EUSI'  : (quad(4.85016, 1.82135, -0.01093),                4.85, 80.62),                               
        'FRUH'  : (loglogw2(1.13547, 2.4092, 0.01081),              1.29, 118.04),                              
        'FRVEG' : (quad(3.02365, 1.59851, -0.01351),                3.02, 50.32),                               
        'GIBI'  : (cub(-0.86799, 2.29723, -0.05924, 0.00068),       1.37, 50.82),                               
        'JAMI'  : (cub(2.00317, 2.47309, -0.05587, 0.00051),        2, 69.4),                                   
        'LAIN'  : (lin(2.78513, 0.48853),                           2.79, 34.54),                               
        'LIST'  : (quad(2.48674, 1.32423, -0.00653),                2.49, 69.6),                                
        'LITU'  : (cub(1.97704, 2.27475, -0.05281, 0.00057),        1.98, 83.06),                               
        'MAGR'  : (cub(2.24478, 1.27655, -0.01904, 0.00022),        2.24, 76.34),                               
        'PIBR2' : (cub(5.28421, -1.37336, 0.41881, -0.01147),       4.12, 22.12), # max_age lowered             
        'PICA'  : (cub(0.97362, 2.63793, -0.05828, 0.00111),        0.97, 84.36),                               
        'PICH'  : (cub(2.61799, 2.05051, -0.091, 0.00195),          2.62, 38.97),                               
        'PLAC'  : (quad(3.0111, 1.97885, -0.01805),                 3.01, 55.01), # max_age lowered             
        'PLRA'  : (quad(2.84648, 1.95623, -0.00876),                2.85, 90.47),                               
        'PYCA'  : (cub(2.99896, 0.27152, 0.10985, -0.00264),        3, 29), # max_age lowered                   
        'QUAG'  : (quad(3.18134, 1.27341, -0.00314),                3.18, 114.72),                              
        'QUIL2' : (lin(0.76093, 1.36553),                           0.76, 84.06),                               
        'SCMO'  : (lin(3.19622, 1.05121),                           3.2, 114.62),                               
        'SCTE'  : (lin(3.93912, 1.0768),                            3.94, 70.7),                                
    },                                                                                                          
    'InlValMOD': {  # InlVal                                                                                    
        'ACSA1' : (lin(2.51245, 1.6505),                            2.51, 126.3),                               
        'BEPE'  : (lin(2.53121, 0.87957),                           2.53, 47.39),                               
        'CESI4' : (quad(2.5184, 2.16011, -0.01839),                 2.52, 58.52), # max_age lowered             
        'CICA'  : (quad(2.52476, 1.52318, -0.00624),                2.52, 95.47),                               
        'FRAN_R': (quad(2.51452, 2.54844, -0.03194),                2.51, 39.51), # max_age lowered             
        'FREXH' : (lin(3.06926, 1.12052),                           3.07, 70.3),                                
        'FRHO'  : (quad(2.51709, 2.29152, -0.01509),                2.52, 75.52), # max_age lowered             
        'FRPEM' : (quad(2.52274, 1.72537, -0.01816),                2.52, 43.49),                               
        'FRVEG' : (quad(2.52059, 1.94085, -0.01297),                2.52, 75.13),                               
        'GIBI'  : (cub(2.54104, -0.10418, 0.0531, -0.00052),        2.49, 67.49), # max_age lowered             
        'GLTR'  : (lin(2.5264, 1.36037),                            2.53, 70.55),                               
        'KOPA'  : (quad(2.53372, 0.62574, 0.01098),                 2.53, 61.28),                               
        'LAIN'  : (lin(2.53611, 0.38823),                           2.54, 35.15),                               
        'LIST'  : (lin(2.52804, 1.19535),                           2.53, 80.23),                               
        'MAGR'  : (lin(2.53226, 0.77382),                           2.53, 55.15),                               
        'PICH'  : (quad(2.52667, 1.334, -0.00875),                  2.53, 53.36),                               
        'PITH'  : (cub(2.51167, 2.83381, -0.07872, 0.00074),        2.51, 40.32),                               
        'PLAC'  : (cub(2.74346, 2.76313, -0.04948, 0.0003),         2.74, 55.57),                               
        'PRCE'  : (loglogw3(2.66607, 0.37611, 0.00299),             12.55, 25.01),
        'PYCA_B': (quad(2.52151, 1.84816, -0.02253),                2.52, 40.43),                               
        'QUIL2' : (lin(2.52584, 1.41611),                           2.53, 115.81),                              
        'ZESE'  : (quad(2.52361, 1.63788, -0.00855),                2.52, 77.25),                               
    },                                                                                                          
    'InterWABQ': {  # InterW                                                                                    
        'CHLI'  : (lin(4.29705, 0.92975),                           4.3, 41.49),                                
        'ELAN'  : (loglogw2(1.23943, 2.09658, 0.03678),             1.63, 80.74),                               
        'FRAM'  : (lin(0.94594, 1.49623),                           2.44, 75.76),                               
        'FRAN2' : (quad(3.77994, 1.42036, -0.01059),                3.78, 51.39),                               
        'FRPE'  : (lin(2.43636, 1.13626),                           2.44, 70.61),                               
        'FRVE'  : (cub(4.61345, 0.39975, 0.05339, -0.00074),        4.61, 51.61), # max_age lowered             
        'GLTR'  : (lin(2.71672, 1.11169),                           2.72, 66.08),                               
        'KOPA'  : (lin(6.15527, 0.704),                             6.16, 50.51),                               
        'MA2'   : (lin(4.26106, 0.71828),                           4.26, 45.2),                                
        'PICH'  : (lin(5.9158, 0.59831),                            5.92, 33.44),                               
        'PIED'  : (lin(5.01376, 0.55731),                           5.01, 36.78),                               
        'PINI'  : (loglogw1(0.60678, 2.7169, 0.0857),               0.8, 77.94),                                
        'PIPO'  : (lin(0.13106, 1.45354),                           1.58, 61.18),                               
        'PISY'  : (lin(6.79183, 0.88852),                           6.79, 56.55),                               
        'PLAC'  : (quad(0.97695, 1.71132, -0.00952),                2.68, 69.39),                               
        'POAN'  : (quad(0.30296, 2.68255, -0.0176),                 2.97, 75.97), # max_age lowered             
        'POFR'  : (cub(-6.42582, 4.08619, -0.07247, 0.00052),       1.46, 120.92),                              
        'PRCE'  : (lin(3.40112, 0.85789),                           3.4, 46.3),                                 
        'PYCA'  : (lin(5.48639, 0.95917),                           5.49, 41.93),                               
        'ULPU'  : (quad(0.79765, 1.81294, -0.00775),                0.8, 105.74),                               
    },                                                                                                          
    'LoMidWXXX': {  # LoMidW                                                                                    
        'ACPL'  : (cub(0.98208, 0.25006, 0.03658, -0.0003),         0.98, 84.98), # max_age lowered             
        'ACRU'  : (quad(-0.2702, 1.45336, -0.00647),                1.18, 81.35),                               
        'ACSA1' : (loglogw1(-0.89552, 3.61294, 0.05324),            1.42, 120.14),                              
        'ACSA2' : (loglogw1(0.16044, 2.68385, 0.08969),             1.68, 80.88),                               
        'CASP'  : (loglogw1(0.73449, 2.4836, 0.06565),              0.94, 104.07),                              
        'CECA'  : (cub(-8.59751, 3.09997, -0.07802, 0.00073),       2.6, 75),                                   
        'CEOC'  : (lin(2.83867, 1.1325),                            2.84, 82.11),                               
        'FRAM'  : (quad(-3.53416, 1.9916, -0.01103),                2.34, 86.36),                               
        'FRPE'  : (loglogw3(0.37847, 2.72552, 0.0012),              1.89, 112.57),                              
        'GLTR'  : (lin(1.85536, 1.13446),                           1.86, 115.3),                               
        'JUNI'  : (loglogw1(0.18691, 2.80787, 0.04201),             1.66, 97.17),                               
        'MA2'   : (lin(2.48841, 1.15593),                           2.49, 60.28),                               
        'MO'    : (loglogw1(-0.06388, 2.93553, 0.08557),            1.38, 96),                                  
        'PIPU'  : (quad(2.12167, 1.60521, -0.00924),                2.12, 53.25),                               
        'PIST'  : (cub(1.87523, 1.11975, -0.01146, 0.00006),        1.88, 67.36),                               
        'PODE'  : (cub(-23.6314, 6.13541, -0.13834, 0.00102),       3.71, 38.71), # max_age lowered             
        'PYCA_B': (lin(4.13514, 1.2698),                            4.14, 54.93),                               
        'QURU'  : (lin(-0.0381, 1.54005),                           1.5, 130.87),                               
        'TICO'  : (loglogw1(0.18526, 2.82231, 0.05631),             1.69, 97.08),                               
        'ULPU'  : (quad(3.76769, 1.89111, -0.0075),                 3.77, 122.68),                              
    },                                                                                                          
    'MidWstMSP': {  # MidWst                                                                                    
        'ACNE'  : (lin(4.2805, 2.10929),                            4.28, 88.65),                               
        'ACPL'  : (cub(-7.94613, 3.80588, -0.09314, 0.00115),       2.66, 93.26),                               
        'ACRU'  : (cub(4.12164, 1.34432, -0.07276, 0.00311),        4.12, 63.03),                               
        'ACSA1' : (cub(-1.7914, 1.88949, 0.06576, -0.00121),        2.24, 47.24), # max_age lowered             
        'ACSA2' : (cub(2.52368, 1.31314, 0.01822, -0.00028),        2.52, 66.52), # max_age lowered             
        'CEOC'  : (cub(3.54797, 1.18435, 0.0522, -0.00081),         3.55, 52.55), # max_age lowered             
        'FRAM'  : (cub(2.83778, 0.75231, 0.15946, -0.00486),        2.84, 23.84), # max_age lowered             
        'FRPE'  : (quad(-2.71787, 2.37818, -0.01186),               1.99, 99.99), # max_age lowered             
        'GIBI'  : (lin(3.58555, 1.14093),                           3.59, 49.22),                               
        'GLTR'  : (cub(4.22795, -0.82484, 0.37243, -0.01051),       3.77, 22.77), # max_age lowered             
        'MA2'   : (cub(3.23454, 1.60114, -0.0723, 0.00185),         3.23, 69.76),                               
        'QUPA'  : (cub(3.31385, -0.16442, 0.14156, -0.00245),       3.29, 38.29), # max_age lowered             
        'QURU'  : (quad(1.99374, 1.63948, -0.00829),                1.99, 68.49),                               
        'TIAM'  : (cub(3.29265, 1.6335, -0.02574, 0.0004),          3.29, 117.21),                              
        'TICO'  : (cub(3.31492, 1.20157, 0.13063, -0.00336),        3.31, 30.31), # max_age lowered             
        'ULAM'  : (quad(3.79547, 1.45324, -0.00293),                3.8, 114.49),                               
        'ULPU'  : (cub(-8.78866, 5.69632, -0.19865, 0.00269),       1.83, 90.8),                                
    },                                                                                                          
    'NMtnPrFNL': {  # NMtnPr                                                                                    
        'ACPL'  : (quad(2.83678, 1.31988, -0.00476),                2.84, 92.73),                               
        'ACSA1' : (quad(2.8327, 1.72872, -0.00484),                 2.83, 140.59),                              
        'ACSA2' : (lin(2.30714, 1.02877),                           2.31, 84.61),                               
        'CEOC'  : (lin(2.83867, 1.1325),                            2.84, 116.09),                              
        'FRAM'  : (cub(2.8422, 0.77951, 0.03184, -0.00039),         2.84, 64.84), # max_age lowered             
        'FRPE'  : (quad(2.83395, 1.44568, -0.00468),                2.83, 99.01),                               
        'GLTR'  : (quad(2.82434, 1.53556, -0.00593),                2.82, 101.75),                              
        'GYDI'  : (lin(2.84088, 0.9127),                            2.84, 66.73),                               
        'MA2'   : (lin(2.48841, 1.15593),                           2.49, 60.28),                               
        'PINI'  : (cub(3.16683, 0.6726, 0.06006, -0.00121),         3.17, 38.17), # max_age lowered             
        'PIPO'  : (quad(2.84126, 1.40282, -0.00741),                2.84, 68.7),                                
        'PIPU'  : (quad(2.12167, 1.60521, -0.00924),                6.85, 71.87),                               
        'POSA'  : (quad(2.833, 1.70027, -0.00515),                  2.83, 136.15),                              
        'PR'    : (lin(1.59016, 1.18497),                           1.59, 31.21),                               
        'PY'    : (quad(3.11411, 1.0985, -0.00964),                 3.11, 33.95),                               
        'QUMA1' : (lin(2.83898, 1.10137),                           2.84, 101.96),                              
        'TIAM'  : (quad(2.83048, 1.41347, -0.0073),                 2.83, 71.25),                               
        'TICO'  : (quad(2.40466, 1.61553, -0.0112),                 2.4, 60.68),                                
        'ULAM'  : (cub(2.88323, 3.06598, -0.05448, 0.00037),        2.88, 112.89),                              
        'ULPU'  : (quad(3.76769, 1.89111, -0.0075),                 3.77, 119.63),                              
    },                                                                                                          
    'NoEastXXX': {  # NoEast                                                                                   
        'ACPL'  : (lin(5.61705, 0.91636),                           5.62, 114.66),                              
        'ACRU'  : (cub(2.64166, 1.27076, -0.01758, 0.00012),        2.64, 105.2),                               
        'ACSA1' : (loglogw1(1.1583, 1.77675, 0.25666),              2.25, 58.49),                               
        'ACSA2' : (lin(2.17085, 0.85396),                           2.17, 105.5),                               
        'AEHI'  : (quad(3.34694, 0.45797, 0.00782),                 3.35, 90.02),                               
        'FRPE'  : (cub(2.41764, 1.4626, -0.02052, 0.00016),         2.42, 123.45),                              
        'GIBI'  : (quad(1.91918, 1.0947, -0.00307),                 1.92, 82.59),                               
        'GLTR'  : (loglogw1(1.68387, 1.59967, 0.06782),             3.23, 71.86),                               
        'LIST'  : (quad(3.42364, 0.88982, -0.00252),                3.42, 80.14),                               
        'MA2'   : (lin(2.84705, 0.74535),                           2.85, 46.08),                               
        'PIST'  : (cub(1.87523, 1.11975, -0.01146, 0.00006),        2.98, 96.1),                                
        'PLAC'  : (quad(2.40322, 1.2942, -0.00705),                 2.4, 61.76),                                
        'PRSE2' : (lin(3.606, 1.53283),                             3.61, 92.51),                               
        'PYCA'  : (lin(4.13514, 1.2698),                            4.14, 54.93),                               
        'QUPA'  : (lin(2.85629, 1.29969),                           2.86, 127.63),                              
        'QUPH'  : (lin(4.16427, 1.14593),                           4.16, 121.05),                              
        'QURU'  : (lin(2.89687, 0.91156),                           2.9, 139.63),                               
        'TICO'  : (cub(2.70741, 1.43292, -0.01191, 0.00006),        2.71, 131.1),                               
        'TITO'  : (loglogw1(1.36034, 1.49373, 0.29856),             3.02, 45.3),                                
        'ULAM'  : (lin(5.28982, 1.31631),                           5.29, 132.97),                              
        'ZESE'  : (lin(2.17317, 1.32424),                           2.17, 81.63),                               
    },                                                                                                          
    'PacfNWLOG': {  # PacfNW                                                                                    
        'ACMA'  : (cub(-0.21317, 1.97429, -0.01051, 0.00003),       1.75, 174.33),                              
        'ACPL'  : (cub(-0.85211, 2.4427, -0.02993, 0.00022),        1.56, 146.78),                              
        'ACRU'  : (lin(-0.28784, 1.61264),                          1.32, 96.47),                               
        'ACSA2' : (cub(1.47953, 1.65885, 0.00513, -0.00015),        1.48, 73.48), # max_age lowered             
        'BEPE'  : (quad(-0.91466, 2.11608, -0.02273),               1.18, 46.18), # max_age lowered             
        'CABEF' : (cub(-0.99936, 2.16074, -0.08853, 0.00412),       3, 51.96),                                  
        'CADE2' : (lin(-0.5418, 2.23052),                           3.92, 50.76),                               
        'CRLA'  : (cub(0.20544, 0.81745, 0.01594, -0.00034),        1.9, 38.23),                                
        'FASY'  : (cub(-2.64454, 3.28563, -0.09364, 0.00158),       3.56, 87.41),                               
        'FRLA'  : (cub(-1.63283, 2.29867, -0.02735, 0.00016),       2.86, 94.09),                               
        'LIST'  : (lin(2.02364, 1.64102),                           2.02, 67.66),                               
        'MOAL'  : (cub(-4.50256, 4.49267, -0.14464, 0.00188),       3.92, 68.25),                               
        'PICO5' : (loglogw2(1.57707, 1.6895, 0.00427),              2.61, 43.46),                               
        'POTR2' : (cub(-0.52236, 1.19511, 0.01779, -0.00011),       1.94, 134.01),                              
        'PRCE'  : (quad(0.78364, 0.88584, -0.00949),                1.66, 21.04),                               
        'PRSE2' : (lin(-0.65197, 1.81238),                          1.16, 79.09),                               
        'PSME'  : (quad(-1.19688, 2.36185, -0.01267),               1.15, 93.15), # max_age lowered             
        'PYAN'  : (quad(0.78363989, 0.885844908, -0.009487773),     0.78, 21.46),                               
        'QURU'  : (cub(0.12978, 1.83846, 0.02001, -0.00036),        1.99, 63.99), # max_age lowered             
        'TIAM'  : (cub(-0.57558, 1.6899, 0.00442, -0.00016),        1.12, 69.12), # max_age lowered             
        'TICO'  : (cub(-0.74132, 1.99578, -0.02803, 0.00027),       1.23, 125.41),                              
        'ULAM'  : (quad(-0.70738, 1.81652, -0.00501),               1.1, 138.55),                               
    },                                                                                                          
    'PiedmtCLT': {  # Piedmt                                                                                    
        'ACRU'  : (quad(4.18772, 1.27754, 0.01399),                 4.19, 122.46),                              
        'ACSA1' : (lin(1.29639, 2.10889),                           1.3, 127.83),                               
        'ACSA2' : (cub(-1.68001, 2.32536, -0.00094, -0.00023),      0.64, 56.64), # max_age lowered             
        'BENI'  : (lin(-1.17183, 2.12321),                          0.95, 73.14),                               
        'COFL'  : (lin(-2.14081, 1.79176),                          1.44, 51.61),                               
        'ILOP'  : (lin(0.35018, 0.91075),                           1.26, 55),                                  
        'JUVI'  : (loglogw1(0.21415, 2.93762, 0.02967),             3.34, 85.95),                               
        'LA6'   : (cub(2.53768, 0.23253, 0.10404, -0.002),          2.54, 35.54), # max_age lowered             
        'LIST'  : (lin(-1.80388, 2.05295),                          2.3, 121.37),                               
        'MA2'   : (loglogw2(0.85023, 2.63523, 0.00902),             3.02, 89.12),                               
        'MAGR'  : (quad(3.0608, 1.05288, 0.00956),                  3.06, 83.65),                               
        'PIEC'  : (quad(-3.10659, 1.97198, -0.00404),               2.77, 69.3),                                
        'PITA'  : (loglogw1(-0.02355, 3.26141, 0.0065),             1.34, 70.69),                               
        'PR'    : (quad(1.665, 1.66173, 0.0343),                    1.67, 82.39),                               
        'PRYE'  : (loglogw1(0.85405, 2.79754, 0.11221),             1.05, 73.46),                               
        'PYCA'  : (lin(0.74946, 1.82157),                           0.75, 55.4),                                
        'QUAL'  : (lin(-0.48742, 1.81656),                          1.33, 123.04),                              
        'QUNI'  : (cub(4.51977, 1.26018, 0.02646, -0.00032),        4.52, 73.52), # max_age lowered             
        'QUPH'  : (quad(-1.96949, 2.12788, -0.00773),               2.26, 110.14),                              
        'QURU'  : (lin(3.86968, 1.73866),                           3.87, 96.02),                               
        'ULAL'  : (lin(-5.25658, 2.39512),                          1.93, 90.55),                               
    },                                                                                                          
    'SacVal': {  # Not an i-Tree region??                                                                       
        'CEDE'  : (loglogw1(0.60029, 2.65795, 0.06116),             0.77, 100.42),                              
        'CEOC'  : (quad(0.59486, 1.77385, -0.0115),                 2.36, 69.02),                               
        'CESI4' : (cub(0.83516, 2.40233, -0.04183, 0.00036),        3.2, 114.37),                               
        'CICA'  : (quad(2.9586, 1.90342, -0.0066),                  2.96, 133.79),                              
        'FRVE'  : (cub(1.22216, 3.08089, -0.06277, 0.00055),        1.22, 116.04),                              
        'GIBI'  : (cub(0.45133, 1.73857, -0.02112, 0.00013),        2.17, 120.81),                              
        'LAIN'  : (cub(2.02636, 1.21727, -0.02189, 0.00019),        2.03, 40.37),                               
        'LIST'  : (quad(3.71462, 1.76501, -0.0092),                 3.71, 88.39),                               
        'LITU'  : (cub(1.77312, 2.34134, -0.03313, 0.00026),        1.77, 104.81),                              
        'MAGR'  : (loglogw1(0.8897, 2.29879, 0.07535),              1.18, 89.25),                               
        'PICH'  : (loglogw1(1.08846, 2.11365, 0.04575),             1.47, 76.05),                               
        'PLAC'  : (quad(3.52669, 1.43849, -0.00343),                3.53, 126.7),                               
        'PRCE'  : (loglogw1(1.41379, 1.62752, 0.05803),             0.01, 41.51),                               
        'PYCA'  : (loglogw1(1.84201, 1.59266, 0.03767),             0.77, 60.9),                                
        'QUAG'  : (cub(2.25596, 1.43382, 0.01147, -0.00018),        2.26, 77.26), # max_age lowered             
        'QULO'  : (cub(2.28211, 1.66463, -0.01025, 0.00002),        2.28, 133.28), # max_age lowered            
        'QURU'  : (quad(3.22204, 1.76438, -0.009),                  3.22, 89.67),                               
        'SESE'  : (lin(-0.95197, 2.68361),                          1.73, 173.48),                              
        'ULPA'  : (cub(2.3358, 2.08455, -0.02888, 0.00023),         2.34, 104.3),                               
        'ZESE'  : (quad(1.32502, 2.13762, -0.00791),                1.33, 121.72),                              
    },                                                                                                          
    'SoCalCSMA': {  # SoCalC                                                                                    
        'CACI'  : (lin(2.53402, 0.59754),                           2.53, 35.4),                                
        'CEDE'  : (quad(0.92345, 1.42681, 0.01585),                 0.92, 111.88),                              
        'CESI3' : (quad(2.53495, 0.50529, 0.01848),                 2.53, 86.24),                               
        'CICA'  : (lin(2.52669, 1.33056),                           2.53, 115.62),                              
        'CUAN'  : (quad(1.30481, 1.3781, -0.00872),                 1.3, 55.64),                                
        'EUFI81': (quad(2.53379, 0.62042, 0.0238),                  2.53, 108.66),                              
        'FIMI'  : (cub(2.50388, 3.61389, -0.12425, 0.00163),        2.5, 79.95),                                
        'JAMI'  : (lin(2.67791, 0.78174),                           2.68, 61.31),                               
        'LIST'  : (loglogw1(1.17646, 1.72145, 0.04807),             1.83, 45.52),                               
        'MAGR'  : (cub(2.53724, 0.27511, 0.03873, -0.00048),        2.54, 55.89),                               
        'MEEX'  : (cub(2.52273, 1.72789, -0.04419, 0.00073),        2.52, 85.16),                               
        'MEQU'  : (quad(2.52993, 1.00644, 0.01677),                 2.53, 81.79),                               
        'PICA'  : (loglogw3(1.71521, 1.8228, 0.00156),              2.85, 90.44),                               
        'PIUN'  : (quad(2.53813, 0.18654, 0.02801),                 2.54, 81.89),                               
        'POMA'  : (lin(2.53994, 0.57161),                           2.54, 36.84),                               
        'PRCA'  : (quad(2.52668, 1.33198, -0.01598),                2.53, 30.24),                               
        'SCTE'  : (quad(2.52131, 1.8692, -0.01987),                 2.52, 46.48),                               
        'TRCO'  : (lin(4.67682, 0.69794),                           4.68, 39.57),                               
    },                                                                                                          
    'SWDsrtGDL': {  # SWDsrt                                                                                    
        'ACFA'  : (lin(2.52897, 1.10273),                           2.53, 46.64),                               
        'ACSA3' : (lin(2.52259, 1.74138),                           2.52, 63.47),                               
        'BRPO'  : (cub(2.52375, 1.62224, -0.03307, 0.00025),        2.52, 68.4),                                
        'CEFL'  : (lin(2.52876, 1.11943),                           2.53, 41.71),                               
        'CHLI'  : (lin(2.54375, 0.96983),                           2.54, 53.94),                               
        'EUMI2' : (lin(2.55896, 1.83486),                           2.56, 85.13),                               
        'FRUH'  : (quad(2.53294, 0.70649, 0.01868),                 2.53, 72.15),                               
        'FRVE'  : (expow1(1.71976, 0.05882, 0.1485),                6.01, 84.87),                               
        'MOAL'  : (cub(0.58767, 1.3122, 0.00991, -0.00014),         1.91, 83.91), # max_age lowered             
        'OLEU'  : (quad(2.52528, 1.47098, -0.00821),                2.53, 68.39),                               
        'PAAC'  : (quad(2.53333, 0.66515, 0.01885),                 2.53, 70.64),                               
        'PICH'  : (lin(2.54739, 1.01967),                           2.55, 63.73),                               
        'PIEL2' : (lin(2.53046, 0.95334),                           2.53, 50.2),                                
        'PIHA'  : (lin(2.52414, 1.58514),                           2.52, 99.22),                               
        'PRCH'  : (lin(2.52292, 1.7092),                            2.52, 70.89),                               
        'QUVI'  : (quad(1.90461, 0.50957, 0.03739),                 1.9, 38.01),                                
        'RHLA'  : (lin(2.52775, 1.22711),                           2.53, 67.56),                               
        'ULPA'  : (lin(2.53344, 1.02077),                           2.53, 53.57),                               
    },                                                                                                          
    'TpIntWBOI': {  # TpIntW                                                                                    
        'ACPL'  : (cub(4.41828, 1.08423, 0.00805, -0.00012),        4.42, 79.42),                               
        'ACSA1' : (cub(4.03735, 0.99779, 0.01328, -0.00011),        4.04, 108.04), # max_age lowered            
        'ACSA2' : (cub(3.57791, 0.71647, 0.01416, -0.00015),        3.58, 76.42),                               
        'CASP'  : (loglogw1(0.73449, 2.4836, 0.06565),              2.83, 101.83),                              
        'CR'    : (quad(-0.56542, 1.3042, -0.00925),                2.01, 45.39),                               
        'FRAM'  : (cub(-8.43051, 2.79568, -0.04049, 0.00024),       2.12, 105.58),                              
        'FRPE'  : (quad(-0.36183, 1.32795, -0.00476),               2.28, 89.44),                               
        'GLTR'  : (cub(2.49094, 1.2233, 0.00418, -0.00008),         2.49, 85.84),                               
        'JUNI'  : (loglogw1(0.18691, 2.80787, 0.04201),             1.66, 97.17),                               
        'LIST'  : (quad(-0.08849, 1.4597, -0.00763),                2.8, 68.89),                                
        'MA2'   : (loglogw1(-0.67733, 3.46698, 0.02178),            1.62, 64.08),                               
        'PIPU'  : (quad(1.20424, 1.32915, -0.00508),                1.2, 86.89),                                
        'PISY'  : (loglogw1(-1.8372, 4.4246, 0.04216),              1.39, 80.31),                               
        'PLAC'  : (cub(3.16755, 1.9672, -0.02191, 0.00013),         3.17, 122.97),                              
        'PLOC'  : (loglogw1(0.57189, 2.61632, 0.05324),             2.41, 113.39),                              
        'PYCA'  : (quad(3.6938, 0.52826, 0.02922),                  3.69, 57.98),                               
        'QURU'  : (cub(3.65573, 0.81496, 0.01359, -0.00015),        3.66, 78.92),                               
        'ROPS'  : (cub(2.53091, 0.90726, 0.02391, -0.00026),        2.53, 76.53), # max_age lowered             
        'TIAM'  : (quad(0.17199, 1.56439, -0.00867),                3.27, 70.72),                               
        'ULPU'  : (cub(-2.208, 1.87431, 0.00437, -0.00016),         1.56, 72.56), # max_age lowered             
    },                                                                                                          
    'TropicPacXXX': {  # Tropic                                                                                 
        'BABL'  : (quad(2.41229, 1.26996, -0.0104),                 2.41, 41.2),                                
        'CAEQ'  : (lin(2.44092, 0.99003),                           2.44, 116.29),                              
        'CAIN4' : (quad(2.38911, 1.11176, -0.00166),                2.39, 98.56),                               
        'CANE33': (lin(2.38894, 1.10447),                           3.49, 78.6),                                
        'CISP2' : (cub(2.19465, 2.1309, -0.07159, 0.00095),         2.19, 70.4),                                
        'COERA2': (quad(1.95348, 0.46074, 0.02779),                 1.95, 88.1),                                
        'COSU2' : (quad(2.28654, 1.39468, -0.01038),                2.29, 49.15),                               
        'DERE'  : (quad(1.64273, 1.65829, -0.0098),                 1.64, 71.78),                               
        'ELOR2' : (lin(2.41656, 0.83335),                           2.42, 60.75),                               
        'FIBE'  : (cub(2.24394, 1.91147, -0.02323, 0.00013),        4.13, 108.41),                              
        'FIDE6' : (lin(0.5342, 1.04288),                            1.58, 61.02),                               
        'ILPA2' : (cub(1.679, 1.21217, -0.03124, 0.00037),          1.68, 45.67),                               
        'LASP'  : (quad(2.41782, 0.81691, 0.0085),                  2.42, 64.51),                               
        'MEQU'  : (lin(2.35634, 1.43309),                           2.36, 81.18),                               
        'PISA2' : (cub(2.98761, 4.07216, -0.08138, 0.00062),        2.99, 165.34),                              
        'SWMA'  : (cub(2.26942, 2.31136, -0.04595, 0.00035),        2.27, 120.43),                              
        'TAAR'  : (lin(1.57113, 1.11663),                           1.57, 57.4),                                
        'TACH4' : (lin(2.37808, 1.20433),                           2.38, 74.64),                               
        'TAPA'  : (lin(2.37428, 1.19672),                           2.37, 72.98),                               
    },
}
