from custom_types import GoogleUserMetrics, DBGooglePointSystem
from collections import defaultdict
from typing import cast


class GoogleScoreCalculator:

    def process_devices(self, user_devices) -> tuple[int, float]:
        non_corp_devices = set()
        platform = defaultdict(lambda: 0)
        for device in user_devices:
            if device["ownership"] == "BYOD":
                non_corp_devices.add(device["device_id"])
            platform[device["platform"]] += 1

        windows = platform.get("WINDOWS", 0)
        all_platforms = sum(value for key, value in platform.items())
        total = 1 if all_platforms == 0 else all_platforms

        return len(non_corp_devices), (windows / total)

    def calculate_scores(
        self,
        user_metrics: GoogleUserMetrics,
        points: list[DBGooglePointSystem],
        max_accumulation: int = 10,
    ) -> float:
        user_score = 0
        processed_points = {elem["label"]: elem["points"] for elem in points}
        bad_practices = [
            "reused_pwds",
            "unsafe_sites",
            "risky_downloads",
            "non_corp_devices",
            "files_public_link",
            "vulnerable_pwds",
            "malware_downloads",
        ]
        good_practices = [
            "messages_conf",
            "enabled_2sv",
            "files_exp_date",
            "device_platform",
        ]
        for label, value in user_metrics.items():
            if label in bad_practices and value == 0:
                user_score += processed_points.get(label, 0)
            elif label in good_practices:
                if cast(int, value) > max_accumulation:
                    user_score += (
                        processed_points.get(label, 0) * max_accumulation
                    )
                else:
                    user_score += processed_points.get(label, 0) * cast(
                        float | int | bool, value
                    )

        return user_score
