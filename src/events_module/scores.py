from custom_types import EventMetrics


class EventScoreCalculator:
    def process_events(self, events):
        return

    def calculate_scores(self, events: dict[str, EventMetrics], points):
        processed_points = {
            elem["label"]: {
                "points": elem["points"],
                "minimum": elem["minimum"],
            }
            for elem in points
        }
        good_practices = {"restart", "lock_screen", "updates"}
        bad_practices = {"usb_devices", "login_failed"}
        biometrics = {"biometric_auth", "login_sucess"}
        user_scores = {}
        for user_email, metrics in events.items():
            score = 0
            for label, value in metrics.items():
                if label in biometrics:
                    if metrics["biometric_auth"] > metrics["login_success"]:
                        score += processed_points["biometric_auth"]["points"]
                elif (
                    label in good_practices
                    and value >= processed_points[label]["minimum"]
                ):
                    score += processed_points[label]["points"]
                elif (
                    label in bad_practices
                    and value <= processed_points[label]["minimum"]
                ):
                    score += processed_points[label]["points"]
            user_scores[user_email] = score

        return user_scores
