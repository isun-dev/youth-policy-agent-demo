from __future__ import annotations

import unittest

from app.schemas import EligibilityResult, EligibilityStatus, Policy, UserProfile
from app.slot_filling import (
    choose_slot_filling_result,
    choose_slot_filling_result_by_user,
    fill_slots_for_result,
    parse_slot_answer,
    should_continue_slot_filling,
)


class SlotFillingTest(unittest.TestCase):
    def test_parse_slot_answer(self) -> None:
        self.assertIs(parse_slot_answer("예"), True)
        self.assertIs(parse_slot_answer("아니오"), False)
        self.assertIsNone(parse_slot_answer("모름"))

    def test_chooses_first_available_policy_without_user_selection(self) -> None:
        regular_result = _result("청년주택드림청약통장", ["income_level"])
        guarantee_result = _result("전세보증금반환보증 보증료 지원", ["housing_status"])

        chosen = choose_slot_filling_result([regular_result, guarantee_result])

        self.assertIs(chosen, regular_result)

    def test_user_can_choose_slot_filling_policy_by_number(self) -> None:
        regular_result = _result("청년주택드림청약통장", ["income_level"])
        guarantee_result = _result("전세보증금반환보증 보증료 지원", ["housing_status"])

        chosen = choose_slot_filling_result_by_user(
            [regular_result, guarantee_result],
            input_func=lambda _: "2",
            print_func=lambda _: None,
        )

        self.assertIs(chosen, guarantee_result)

    def test_user_can_skip_policy_selection(self) -> None:
        result = _result("청년주택드림청약통장", ["income_level"])

        chosen = choose_slot_filling_result_by_user(
            [result],
            input_func=lambda _: "0",
            print_func=lambda _: None,
        )

        self.assertIsNone(chosen)

    def test_skips_excluded_policy_ids(self) -> None:
        regular_result = _result("청년주택드림청약통장", ["income_level"])
        guarantee_result = _result("전세보증금반환보증 보증료 지원", ["housing_status"])

        chosen = choose_slot_filling_result(
            [regular_result, guarantee_result],
            excluded_policy_ids={guarantee_result.policy.id},
        )

        self.assertIs(chosen, regular_result)

    def test_fill_slots_updates_profile_extra(self) -> None:
        result = _result(
            "전세보증금반환보증 보증료 지원",
            ["housing_status", "lease_contract", "lease_deposit"],
        )
        answers = iter(["예", "아니오", "모름"])
        profile = UserProfile(age=26, region="경기도 의정부", employment_status="unemployed")

        updated = fill_slots_for_result(
            profile,
            result,
            input_func=lambda _: next(answers),
            print_func=lambda _: None,
        )

        self.assertEqual(
            updated.extra,
            {
                "housing_status": True,
                "lease_contract": False,
                "lease_deposit": None,
            },
        )

    def test_should_continue_slot_filling(self) -> None:
        self.assertTrue(
            should_continue_slot_filling(
                input_func=lambda _: "예",
                print_func=lambda _: None,
            )
        )
        self.assertFalse(
            should_continue_slot_filling(
                input_func=lambda _: "아니오",
                print_func=lambda _: None,
            )
        )

    def test_should_stop_slot_filling_on_eof(self) -> None:
        def raise_eof(_: str) -> str:
            raise EOFError

        self.assertFalse(
            should_continue_slot_filling(
                input_func=raise_eof,
                print_func=lambda _: None,
            )
        )


def _result(policy_name: str, missing_fields: list[str]) -> EligibilityResult:
    return EligibilityResult(
        policy=Policy(id=policy_name, name=policy_name),
        status=EligibilityStatus.NEED_MORE_INFO,
        missing_fields=missing_fields,
    )


if __name__ == "__main__":
    unittest.main()
