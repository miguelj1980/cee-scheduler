"""
CEE Course Scheduling Conflict Calculator
==========================================

This module calculates scheduling conflicts based on:
- Student course demand (likelihood-weighted)
- Time slot overlaps
- Day pattern conflicts

Author: Generated for UC Davis CEE Department
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Set, Tuple

def day_patterns_conflict(pattern1: str, pattern2: str) -> bool:
    """
    Check if two day patterns share any common days.

    Valid patterns: MW, WF, MF, TR

    Conflict rules:
        MW = {M, W}
        WF = {W, F}
        MF = {M, F}
        TR = {T, R}

    Examples:
        MW and WF conflict (share W)
        MW and MF conflict (share M)
        WF and MF conflict (share F)
        MF and MW conflict (share M)
        MF and WF conflict (share F)
        MW and TR don't conflict (no shared days)
        TR only conflicts with TR
    """
    days1 = set(pattern1)
    days2 = set(pattern2)
    return len(days1.intersection(days2)) > 0


def times_overlap(start1: str, end1: str, start2: str, end2: str) -> bool:
    """
    Check if two time ranges overlap.

    Args:
        start1, end1: First time range in HH:MM format
        start2, end2: Second time range in HH:MM format

    Returns:
        True if ranges overlap, False otherwise
    """
    def time_to_minutes(time_str: str) -> int:
        h, m = map(int, time_str.split(':'))
        return h * 60 + m

    s1 = time_to_minutes(start1)
    e1 = time_to_minutes(end1)
    s2 = time_to_minutes(start2)
    e2 = time_to_minutes(end2)

    return s1 < e2 and s2 < e1


def offerings_conflict(offering1: Dict, offering2: Dict) -> bool:
    """
    Check if two course offerings conflict.

    Offerings conflict if they:
    1. Share at least one day (day patterns conflict)
    2. Have overlapping time slots
    """
    if not day_patterns_conflict(offering1['day_pattern'], offering2['day_pattern']):
        return False

    return times_overlap(
        offering1['start_time'], offering1['end_time'],
        offering2['start_time'], offering2['end_time']
    )


def calculate_conflicts(schedule_df: pd.DataFrame, 
                       student_plans_df: pd.DataFrame, 
                       students_df: pd.DataFrame) -> Dict:
    """
    Calculate comprehensive conflict metrics for a given schedule.

    Args:
        schedule_df: Course schedule with columns:
            - course_code: e.g., 'ECI 130'
            - day_pattern: e.g., 'MW', 'TR', 'WF', 'MF'
            - start_time: e.g., '10:00'
            - end_time: e.g., '12:00'
            - term: e.g., '2026FA'

        student_plans_df: Student course plans with columns:
            - student_id
            - course_code
            - term
            - likelihood: 0.0 to 1.0
            - path_type: e.g., 'Structures', 'Undeclared'

        students_df: Student roster with columns:
            - student_id
            - name
            - year: FR, SO, JR, SR
            - path_type

    Returns:
        Dictionary with conflict metrics including:
        - Overall expected conflicts (likelihood-weighted)
        - Number of students with at least one conflict
        - Breakdown by path_type
        - Top conflicting course pairs
        - Top conflicting individual courses
    """

    # Filter student plans to terms in schedule
    terms_in_schedule = schedule_df['term'].unique()
    plans = student_plans_df[student_plans_df['term'].isin(terms_in_schedule)].copy()

    # Map course codes to offerings
    course_to_offering = {}
    for _, row in schedule_df.iterrows():
        course_to_offering[row['course_code']] = {
            'day_pattern': row['day_pattern'],
            'start_time': row['start_time'],
            'end_time': row['end_time'],
            'term': row['term']
        }

    # Initialize metrics
    total_expected_conflicts = 0.0
    students_with_conflict = set()
    conflicts_by_path = {}
    conflicts_by_course = {}
    conflicts_by_pair = {}

    # Process each student
    for student_id in plans['student_id'].unique():
        student_courses = plans[plans['student_id'] == student_id]
        student_info = students_df[students_df['student_id'] == student_id].iloc[0]
        path_type = student_info['path_type']

        # Initialize path metrics
        if path_type not in conflicts_by_path:
            conflicts_by_path[path_type] = {
                'expected_conflicts': 0.0,
                'students_with_conflict': set()
            }

        # Get scheduled courses for this student
        student_scheduled_courses = []
        for _, plan_row in student_courses.iterrows():
            course_code = plan_row['course_code']
            if course_code in course_to_offering:
                student_scheduled_courses.append({
                    'course_code': course_code,
                    'likelihood': plan_row['likelihood'],
                    'offering': course_to_offering[course_code]
                })

        # Check all pairs for conflicts
        student_has_conflict = False
        for i, course1 in enumerate(student_scheduled_courses):
            for course2 in student_scheduled_courses[i+1:]:
                if offerings_conflict(course1['offering'], course2['offering']):
                    # Weighted conflict
                    conflict_weight = course1['likelihood'] * course2['likelihood']
                    total_expected_conflicts += conflict_weight
                    conflicts_by_path[path_type]['expected_conflicts'] += conflict_weight
                    student_has_conflict = True

                    # Track by course
                    for course_code in [course1['course_code'], course2['course_code']]:
                        if course_code not in conflicts_by_course:
                            conflicts_by_course[course_code] = 0.0
                        conflicts_by_course[course_code] += conflict_weight

                    # Track by pair
                    pair = tuple(sorted([course1['course_code'], course2['course_code']]))
                    if pair not in conflicts_by_pair:
                        conflicts_by_pair[pair] = 0.0
                    conflicts_by_pair[pair] += conflict_weight

        if student_has_conflict:
            students_with_conflict.add(student_id)
            conflicts_by_path[path_type]['students_with_conflict'].add(student_id)

    # Format results
    by_path_list = []
    for path_type, metrics in conflicts_by_path.items():
        total_in_path = len(students_df[students_df['path_type'] == path_type])
        by_path_list.append({
            'path_type': path_type,
            'expected_conflicts': round(metrics['expected_conflicts'], 2),
            'students_with_conflict': len(metrics['students_with_conflict']),
            'total_students_in_path': total_in_path,
            'conflict_rate': round(len(metrics['students_with_conflict']) / total_in_path * 100, 1) if total_in_path > 0 else 0
        })

    # Top conflicting pairs
    top_pairs = sorted(conflicts_by_pair.items(), key=lambda x: x[1], reverse=True)[:10]
    top_pairs_formatted = [
        {
            'course_a': pair[0],
            'course_b': pair[1],
            'expected_conflicts': round(weight, 2)
        }
        for pair, weight in top_pairs
    ]

    # Top conflicting courses
    top_courses = sorted(conflicts_by_course.items(), key=lambda x: x[1], reverse=True)[:10]
    top_courses_formatted = [
        {'course_code': course, 'conflict_score': round(score, 2)}
        for course, score in top_courses
    ]

    return {
        'term': list(terms_in_schedule),
        'total_students': len(students_df),
        'courses_in_schedule': len(schedule_df),
        'metrics': {
            'expected_conflicts_all': round(total_expected_conflicts, 2),
            'students_with_conflict': len(students_with_conflict),
            'conflict_rate_overall': round(len(students_with_conflict) / len(students_df) * 100, 1),
            'by_path_type': sorted(by_path_list, key=lambda x: x['expected_conflicts'], reverse=True),
            'top_conflicting_pairs': top_pairs_formatted,
            'top_conflicting_courses': top_courses_formatted
        }
    }
