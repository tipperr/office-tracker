import calendar
import math
import unittest
from datetime import date

import calc


def month_days(year, month):
    return [
        {
            "date": date(year, month, day_number),
            "status": "NONE",
            "is_holiday": False,
        }
        for day_number in range(1, calendar.monthrange(year, month)[1] + 1)
    ]


def set_day(days, day_number, status="NONE", is_holiday=False):
    day = next(item for item in days if item["date"].day == day_number)
    day["status"] = status
    day["is_holiday"] = is_holiday


class ComputeSummaryTests(unittest.TestCase):
    def test_new_work_modes_formula_and_breakdown(self):
        days = month_days(2026, 4)
        set_day(days, 1, "IN_OFFICE")
        set_day(days, 2, "OFFSITE_WORK")
        set_day(days, 3, "VACATION")
        set_day(days, 4, "TRAINING")  # Weekend extra credit.
        set_day(days, 6, "SICK")
        set_day(days, 7, "VOLUNTEER")
        set_day(days, 8, "WFH", is_holiday=True)
        set_day(days, 9, "VACATION", is_holiday=True)  # Must not double-count.
        set_day(days, 10, "COMPANY_HOLIDAY")

        summary = calc.compute_summary(
            days,
            {"required_percent": 0.60, "rounding_mode": "ceil"},
        )

        self.assertEqual(summary["in_person_work_days"], 3)
        self.assertEqual(summary["pto_days"], 4)
        self.assertEqual(summary["company_holidays"], 2)
        self.assertEqual(summary["numerator"], 9)
        self.assertEqual(summary["denominator"], 22)
        self.assertEqual(summary["required_days"], math.ceil(22 * 0.60))
        self.assertEqual(summary["balance"], 9 - math.ceil(22 * 0.60))
        self.assertAlmostEqual(summary["percent_achieved"], 9 / 22 * 100)

    def test_denominator_uses_all_weekdays_in_month_for_partial_data(self):
        summary = calc.compute_summary(
            [{"date": date(2026, 4, 1), "status": "IN_OFFICE"}],
            {"required_percent": 0.60},
        )

        self.assertEqual(summary["workdays"], 22)
        self.assertEqual(summary["denominator"], 22)

    def test_holiday_credit_does_not_depend_on_legacy_weekday_settings(self):
        days = month_days(2026, 4)
        set_day(days, 6, "WFH", is_holiday=True)  # Monday.
        set_day(days, 10, "WFH", is_holiday=True)  # Friday.

        summary = calc.compute_summary(
            days,
            {
                "credit_weekdays": [],
                "monfri_holiday_treatment": "neutral",
                "required_percent": 0.60,
            },
        )

        self.assertEqual(summary["company_holidays"], 2)
        self.assertEqual(summary["numerator"], 2)

    def test_weekend_pto_and_holidays_do_not_count(self):
        days = month_days(2026, 4)
        set_day(days, 4, "SICK", is_holiday=True)
        set_day(days, 5, "OTHER_HOLIDAY", is_holiday=True)

        summary = calc.compute_summary(days, {"required_percent": 0.60})

        self.assertEqual(summary["pto_days"], 0)
        self.assertEqual(summary["company_holidays"], 0)
        self.assertEqual(summary["numerator"], 0)

    def test_legacy_other_holiday_status_still_counts(self):
        days = month_days(2026, 4)
        set_day(days, 10, "OTHER_HOLIDAY")

        summary = calc.compute_summary(days, {"required_percent": 0.60})

        self.assertEqual(summary["company_holidays"], 1)
        self.assertEqual(summary["numerator"], 1)


if __name__ == "__main__":
    unittest.main()
