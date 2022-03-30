"""
    Autotimetabler
"""

import collections
import math
from typing import Tuple

from ortools.sat.python import cp_model

DAY = 0
START_TIME = 1
END_TIME = 2
LOCATION = 3
START = 0
END = 1
FORCE_INCLUDE = 1


class VarArraySolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Print intermediate solutions."""

    def __init__(self, variables):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__variables = variables
        self.__solution_count = 0

    def on_solution_callback(self):
        self.__solution_count += 1
        for v in self.__variables:
            print('%s=%i' % (v, self.Value(v)), end=' ')
        print()

    def solution_count(self):
        return self.__solution_count


def get_int_fp(floating_point):
    """
        Return the decimal value and the floating point values of a number respectively.
    :param floating_point:
    :return:
    """
    return int(floating_point), floating_point - int(floating_point)


class MinuteInterval:
    MINUTES_IN_AN_HOUR = 60
    HOURS_IN_A_DAY = 24
    DAYS_IN_A_WORK_WEEK = 5

    def __init__(self):
        """
            The MinuteInterval Format is basically a list containing the
            interval start and end times in minutes from Monday 00:00 till Friday
            23:59. Assuming that classes can start on the 0th, 15th, 30th, 45th
            minute.

            Furthermore, we can denote a WeekInterval  map as: (24*(n-1) + hour) * 60,
            where n is the day of the week taking Monday as 1st index.
        """
        self._start = 0
        # Effectively 7200 in the week interval and each day is treated in a
        # 1440-minute period.
        self._end = self.HOURS_IN_A_DAY * self.DAYS_IN_A_WORK_WEEK * self.MINUTES_IN_AN_HOUR

    def to_hours(self, minutes: int) -> float:
        return minutes / self.MINUTES_IN_AN_HOUR

    def to_minutes(self, hour: float) -> float:
        return hour * self.MINUTES_IN_AN_HOUR

    def map_day_hour_to_minute_interval(self, day_hour_interval_list: list) -> list:
        """
            This function will take in a day_hour_interval_list list of schematic
            [day, start, end] and return the corresponding time in MinuteInterval
            format [start', end']
        :param day_hour_interval_list:
        :return:
        """
        day_of_the_week = (day_hour_interval_list[DAY] - 1)
        offset_start = day_hour_interval_list[START_TIME]
        offset_end = day_hour_interval_list[END_TIME]
        interval_start = self.MINUTES_IN_AN_HOUR * (day_of_the_week * self.HOURS_IN_A_DAY + offset_start)
        interval_end = self.MINUTES_IN_AN_HOUR * (day_of_the_week * self.HOURS_IN_A_DAY + offset_end)
        return [interval_start, interval_end]

    def map_minute_interval_to_day_hour(self, minute_interval_list: list) -> list:
        """
            This function will take in a week interval list of schematic
            [start', end'] and return the corresponding time in Hour-interval
            format [day, start, end]
            :param minute_interval_list:
            :return:
        """
        assert minute_interval_list[START_TIME - 1] >= 0  # Assumption that the start values are always greater than 0
        assert minute_interval_list[END_TIME - 1] >= 0  # Assumption that the end values are always greater than 0
        hour_interval = [0, 0, 0]  # Day, start_time, end_time
        start_interval = ((minute_interval_list[START_TIME - 1]) / self.MINUTES_IN_AN_HOUR +
                          self.HOURS_IN_A_DAY) / self.HOURS_IN_A_DAY
        end_interval = ((minute_interval_list[END_TIME - 1]) / self.MINUTES_IN_AN_HOUR +
                        self.HOURS_IN_A_DAY) / self.HOURS_IN_A_DAY
        # Explanation:
        #   The mapping is essentially that T: {week_interval_format} => {hour_interval_format}
        #                                       week_interval = 60(24 * (n - 1) + offset)
        #                                   G = 24n + offset  = (week_interval // 60) + 24
        #                                       -> G / 24 = n + offset / 24
        #                                       -> n      = (G - offset) / 24

        day_of_class_start_time, hour_of_class_start_time = get_int_fp(start_interval)
        day_of_class_end_time, hour_of_class_end_time = get_int_fp(end_interval)
        # Assumption that the class starts and ends in the same day.
        assert day_of_class_start_time == day_of_class_end_time
        hour_interval = [day_of_class_start_time,
                         round(hour_of_class_start_time * self.HOURS_IN_A_DAY, 2),
                         round(hour_of_class_end_time * self.HOURS_IN_A_DAY, 2)]
        return hour_interval


def populate_data_set(model: cp_model, mapped_by_course_data_set: list, course_metadata: collections.namedtuple,
                      global_solution_space: list,
                      period_builder: list, course_id: int, classes_id: int) -> tuple[list, list]:
    """
        The purpose of this function is to create variables using the

    :param global_solution_space:
    :param model:
    :param mapped_by_course_data_set:
    :param course_metadata:
    :param period_builder:
    :param course_id:
    :param classes_id:
    :return:
    """
    min_interval_instance = MinuteInterval()
    for period_id in range(len(period_builder)):
        period = period_builder[period_id]
        start_end_list = min_interval_instance.map_day_hour_to_minute_interval(period)
        start = start_end_list[START]
        end = start_end_list[END]
        # The data name for all the variables are going to be of the schematic
        # period_(course id)_(class_id)_(period_id)
        data_name = 'period_%i_%i_%i' % (course_id, classes_id, period_id)
        bool_var = model.NewBoolVar(data_name + '_bool')
        interval_var = model.NewOptionalIntervalVar(start, end - start, end, bool_var, data_name + '_interval')
        # Mutate the list to use the period builder for the tuple containing the model data
        # to save space.
        period_builder[period_id] = course_metadata(course=course_id, start=start, end=end, interval=interval_var,
                                                    location=period[LOCATION], assigned_bool_var=bool_var)
        global_solution_space.append(period_builder[period_id])

    # Conditional channeling, such that there is implication on the existence of
    # all the periods in a given period list.

    for period_id in range(len(period_builder)):
        if period_id == START:
            # Always point to the first period in any given data set since the
            # rest that follows will be implied to always be true.
            print('period_builder:', period_builder[period_id])
            mapped_by_course_data_set[course_id] = mapped_by_course_data_set[course_id] + [period_builder[period_id]]
        else:
            # This is the conditional chaining such that if one period is included in the period set, then the rest
            # follows to be included force fully.
            model.Add(period_builder[period_id].assigned_bool_var == FORCE_INCLUDE).OnlyEnforceIf(
                period_builder[START].assigned_bool_var)

    return global_solution_space, mapped_by_course_data_set


def define_day_time_constraints_for_variables(data: dict, model: cp_model):
    """
        Create the variables that are going to be considered
        for the constraint model.
        :param model:
        :param data: (dict)         - This is a json data which will be scraped for
                                      predetermined fields which is documented.
        :return:
    """
    global_solution_space = []
    course_metadata = collections.namedtuple('course_metadata', 'course start end interval location assigned_bool_var')
    mapped_by_course_data_set = [[]] * len(data['periods'])  # This will house all the course course_metadata variables.
    # define_data_schema = ('course_id', 'class_id', 'period_id', 'location') = IntervalDomainVar
    # Data visualisation Tree
    # Courses
    #   -> Classes
    #       -> Periods
    # Merging consecutive classes.
    days_allowed = list(data['days'])
    days_allowed = list(map(lambda day: int(day), days_allowed))
    for course_id, courses in enumerate(data['periods']):
        for classes_id, classes in enumerate(courses):
            # Go through all the periods and if they are in the days
            # that are restricted, remove them from the data set.
            period_builder = []
            for period_id, period in enumerate(classes):
                if period[DAY] in days_allowed:
                    # Checking whether the day any period in a given
                    # set of classes falls in a day which the
                    # user does not want to attend university.

                    if period[START_TIME] >= int(data['start']) and period[END_TIME] <= int(data['end']):
                        # The given data set is within the feasible conditions that they are within a given
                        period_builder.append(period)

            if period_builder:
                # The given periods in the class constraints to a feasible day and time slot only.
                # We could call the constraint model to constraint the variables but this is another alternative to that
                # method.
                global_solution_space, mapped_by_course_data_set = populate_data_set(model, mapped_by_course_data_set,
                                                                                     course_metadata,
                                                                                     global_solution_space,
                                                                                     period_builder,
                                                                                     course_id, classes_id)
            period_builder.clear()

    return global_solution_space, mapped_by_course_data_set


def define_max_one_class_per_course_constraint(model: cp_model, global_solution_space: list,
                                               mapped_by_course_data_set: list):
    # All the courses need to have exactly one variable that is included in the data set.
    for course_id in range(len(mapped_by_course_data_set)):
        bool_vars = [course_metadata.assigned_bool_var for course_metadata in mapped_by_course_data_set[course_id]]
        model.AddExactlyOne(bool_vars)
        print(bool_vars)


def define_no_overlap_constraint(model: cp_model, global_solution_space: list, mapped_by_course_data_set: list):
    interval_list = []
    for solutions in global_solution_space:
        # Create an interval list which will ensure that none of the chosen
        # variables are overlapping
        interval_list.append(solutions.interval)
    model.AddNoOverlap(interval_list)


def define_min_gap_constraint(model: cp_model, global_solution_space: list, mapped_by_course_data_set: list, gap: int):
    min_intervals = MinuteInterval()
    for i in range(len(global_solution_space) - 1):
        min_gap = min_intervals.to_hours(abs((global_solution_space[i + 1].start - global_solution_space[i].end)))
        print(min_gap)
        model.Add(min_gap >= gap).OnlyEnforceIf(model.AddBoolOr([global_solution_space[i].assigned_bool_var,
                                                                 global_solution_space[i + 1].assigned_bool_var]))


def define_max_days_constraint(model: cp_model, global_solution_space: list, mapped_by_course_data_set: list,
                               max_days: int):
    min_intervals = MinuteInterval()
    sum_day_intervals = 0
    hashset = set()
    different_day_count = 0
    for course_metadata in global_solution_space:
        start = course_metadata.start
        end = course_metadata.end
        day_hour_interval_list = min_intervals.map_minute_interval_to_day_hour([start, end])
        if day_hour_interval_list[DAY] not in hashset:
            different_day_count += 1
            hashset.add(day_hour_interval_list[DAY])
    model.Add(different_day_count <= max_days)


# def get_distance(u, v):
#     distance_matrix = [('a', 'b', 2), ('a', 'c', 3), ('c', 'b', 5)]
#     for i in distance_matrix:
#         if i[0] == u or i[1] == u:
#             if i[0] == v or i[0] == v:
#                 return i[2]
#
#
# class VarArraySolutionPrinter(cp_model.CpSolverSolutionCallback):
#     """Print intermediate solutions."""
#
#     def __init__(self, variables):
#         cp_model.CpSolverSolutionCallback.__init__(self)
#         self.__variables = variables
#         self.__solution_count = 0
#
#     def on_solution_callback(self):
#         self.__solution_count += 1
#         for v in self.__variables:
#             print('%s=%i' % (v, self.Value(v)), end=' ')
#         print()
#
#     def solution_count(self):
#         return self.__solution_count
#
#
def search_optimal_timetable():
    """
        Creating a new model for CP SAT. Using this over
        SCP.
    """
    # data = {
    #     "start": "9",
    #     "end": "19",
    #     "days": "12",
    #     "gap": "1",
    #     "max_days": "2",
    #     "minimum_distance": "True",
    #     "periods":
    #         [
    #             [
    #                 [[5, 11, 12, 'a']],
    #                 [[5, 13, 14, 'a']],
    #                 [[4, 10, 11, 'b']],
    #                 [[4, 14, 15, 'c']],
    #                 [[2, 9, 10, 'b']],
    #                 [[2, 15, 16, 'a']],
    #                 [[3, 12, 13, 'b']]
    #             ],
    #             [
    #                 [
    #                     [1, 17, 18, 'a'],
    #                     [4, 17, 18, 'a']
    #                 ],
    #                 [
    #                     [1, 17, 18, 'b'],
    #                     [4, 17, 18, 'b']
    #                 ],
    #                 [
    #                     [1, 17, 18, 'b'],
    #                     [4, 17, 18, 'b']
    #                 ],
    #                 [
    #                     [1, 18, 19, 'a'],
    #                     [4, 18, 19, 'a']
    #                 ],
    #                 [
    #                     [2, 9, 10, 'a'],
    #                     [4, 9, 10, 'a']
    #                 ],
    #                 [
    #                     [2, 9, 10, 'a'],
    #                     [4, 9, 10, 'a']
    #                 ],
    #                 [
    #                     [2, 9, 10, 'a'],
    #                     [4, 9, 10, 'a']
    #                 ],
    #                 [
    #                     [2, 12, 13, 'a'],
    #                     [4, 12, 13, 'a']
    #                 ],
    #                 [
    #                     [2, 12, 13, 'b'],
    #                     [4, 12, 13, 'b']
    #                 ],
    #                 [
    #                     [2, 12, 13, 'c'],
    #                     [4, 12, 13, 'c']
    #                 ],
    #                 [
    #                     [2, 15, 16, 'a'],
    #                     [4, 15, 16, 'b']
    #                 ],
    #                 [
    #                     [2, 15, 16, 'c'],
    #                     [4, 15, 16, 'c']
    #                 ],
    #                 [
    #                     [2, 15, 16, 'a'],
    #                     [4, 15, 16, 'a']
    #                 ],
    #                 [
    #                     [3, 11, 12, 'a'],
    #                     [5, 11, 12, 'a']
    #                 ],
    #                 [
    #                     [3, 11, 12, 'a'],
    #                     [5, 11, 12, 'a']
    #                 ],
    #                 [
    #                     [3, 11, 12, 'a'],
    #                     [5, 11, 12, 'a']
    #                 ],
    #                 [
    #                     [3, 14, 15, 'a'],
    #                     [5, 14, 15, 'a']
    #                 ],
    #                 [
    #                     [3, 14, 15, 'b'],
    #                     [5, 14, 15, 'b']
    #                 ],
    #                 [
    #                     [3, 14, 15, 'b'],
    #                     [5, 14, 15, 'b']
    #                 ]
    #             ],
    #             [
    #                 [[4, 10, 11, 'c']],
    #                 [[4, 10, 11, 'c']],
    #                 [[2, 9, 10, 'c']],
    #                 [[2, 9, 10, 'b']],
    #                 [[2, 9, 10, 'a']],
    #                 [[2, 9, 10, 'c']],
    #                 [[2, 13, 14, 'c']],
    #                 [[2, 13, 14, 'c']],
    #                 [[2, 13, 14, 'c']],
    #                 [[2, 13, 14, 'c']],
    #                 [[3, 11, 12, 'c']],
    #                 [[3, 11, 12, 'c']],
    #                 [[3, 11, 12, 'c']],
    #                 [[3, 11, 12, 'c']],
    #                 [[3, 16, 17, 'c']],
    #                 [[3, 16, 17, 'c']],
    #                 [[3, 16, 17, 'c']],
    #                 [[3, 16, 17, 'c']]
    #             ]
    #         ]
    # }
    data = {
        "start": "9",
        "end": "24",
        "days": "12345",
        "gap": "2",
        "max_days": "2",
        "minimum_distance": "True",
        "periods":
            [
                [
                    [[3, 14, 15, 'a']],
                    [[4, 11, 12, 'b']],
                ],
                [
                    [
                        [3, 17, 18, 'a'],
                        [4, 14, 18, 'a']
                    ],

                    [
                        [4, 17, 18, 'b'],
                        [3, 14, 18, 'b']
                    ],
                ],
                [
                    [[4, 12, 13, 'c']],
                ]
            ]
    }

    model = cp_model.CpModel()
    # Course mapping for the unique classes.
    global_solution_space, mapped_by_course_data_set = define_day_time_constraints_for_variables(data, model)
    define_max_one_class_per_course_constraint(model, global_solution_space, mapped_by_course_data_set)
    define_no_overlap_constraint(model, global_solution_space, mapped_by_course_data_set)
    define_max_days_constraint(model, global_solution_space, mapped_by_course_data_set, int(data['max_days']))
    #define_min_gap_constraint(model, global_solution_space, mapped_by_course_data_set, int(data['gap']))
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    # solution_printer = VarArraySolutionPrinter(global_solution_space)
    # Enumerate all solutions.
    solver.parameters.enumerate_all_solutions = True
    # Solve.
    status = solver.Solve(model)
    print(solver.StatusName(status))
    # print('Status = %s' % solver.StatusName(status))
    # print('Number of solutions found: %i' % solution_printer.solution_count())


search_optimal_timetable()
