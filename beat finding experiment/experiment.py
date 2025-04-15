# experiment.py (with unconstrained tapping mode)
import json
import os
import tempfile
from functools import cache

from markupsafe import Markup
from repp.analysis import REPPAnalysis
from repp.config import sms_tapping
from repp.stimulus import REPPStimulus
from repp.utils import save_json_to_file, save_samples_to_file

import psynet.experiment
from psynet.asset import CachedFunctionAsset, LocalStorage
from psynet.consent import NoConsent
from psynet.modular_page import AudioPrompt, AudioRecordControl, ModularPage
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Timeline, join, ProgressDisplay, ProgressStage
from psynet.trial.audio import AudioRecordTrial
from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker

from .repp_prescreens import (
    NumpySerializer,
    REPPMarkersTest,
    REPPTappingCalibration,
    REPPVolumeCalibrationMusic,
)

def get_prolific_settings():
    with open("qualification_prolific_en.json", "r") as f:
        qualification = json.dumps(json.load(f))
    return {
        "recruiter": RECRUITER,
        "prolific_estimated_completion_minutes": 10,
        "prolific_recruitment_config": qualification,
        "base_payment": 2.1,
        "auto_recruit": False,
        "currency": "\u00a3",
        "wage_per_hour": 0.01
    }

DEBUG = True
RECRUITER = "prolific"
INITIAL_RECRUITMENT_SIZE = 10
AUTO_RECRUIT = False 
NUM_PARTICIPANTS = 20
DURATION_ESTIMATED_TRIAL = 40

music_stimulus_name = ["music_1", "music_2"]
music_stimulus_audio = ["music/music_1.wav", "music/music_2.wav"]

@cache
def create_music_stim_with_repp(stim_name, audio_filename):
    stimulus = REPPStimulus(stim_name, config=sms_tapping)
    stim_prepared, stim_info, _ = stimulus.prepare_stim_from_files("music")
    info = json.dumps(stim_info, cls=NumpySerializer)
    return stim_prepared, info

def generate_music_stimulus_audio(path, stim_name, audio_filename):
    stim_prepared, _ = create_music_stim_with_repp(stim_name, audio_filename)
    save_samples_to_file(stim_prepared, path, sms_tapping.FS)

def generate_music_stimulus_info(path, stim_name, audio_filename):
    _, info = create_music_stim_with_repp(stim_name, audio_filename)
    save_json_to_file(info, path)

nodes_music = [
    StaticNode(
        definition={"stim_name": name, "audio_filename": audio},
        assets={
            "stimulus_audio": CachedFunctionAsset(generate_music_stimulus_audio),
            "stimulus_info": CachedFunctionAsset(generate_music_stimulus_info),
        },
    )
    for name, audio in zip(music_stimulus_name, music_stimulus_audio)
]

class TapTrialAnalysis(AudioRecordTrial, StaticTrial):
    def get_info(self):
        with tempfile.NamedTemporaryFile() as f:
            self.assets["stimulus_info"].export(f.name)
            with open(f.name, "r") as reader:
                return json.loads(json.load(reader))

    def analyze_recording(self, audio_file: str, output_plot: str):
        info = self.get_info()
        stim_name = info.get("stim_name", "unknown")
        title_in_graph = f"Participant {self.participant_id}"
        analysis = REPPAnalysis(config=sms_tapping)

        audio_signals, extracted_onsets, analysis_data = analysis.do_analysis_tapping_only(
            audio_file, title_in_graph, output_plot
        )

        return {
            "failed": False,
            "reason": None,
            "output": json.dumps(extracted_onsets, cls=NumpySerializer),
            "analysis": json.dumps(analysis_data, cls=NumpySerializer),
            "stim_name": stim_name,
        }

class TapTrialMusic(TapTrialAnalysis):
    time_estimate = DURATION_ESTIMATED_TRIAL

    def get_bot_response_media(self):
        return {
            "music_1": "example_music_tapping_track_1.wav",
            "music_2": "example_music_tapping_track_2.wav",
        }[self.definition["stim_name"]]

    def show_trial(self, experiment, participant):
        info = self.get_info()
        duration_rec = info["stim_duration"]
        trial_number = self.position + 1
        return ModularPage(
            "trial_main_page",
            AudioPrompt(
                self.assets["stimulus_audio"].url,
                Markup(
                    f"""
                    <br><h3>Tap in time with the beat.</h3>
                    Trial number {trial_number}.
                    """
                ),
            ),
            AudioRecordControl(
                duration=duration_rec,
                show_meter=False,
                controls=False,
                auto_advance=False,
                bot_response_media=self.get_bot_response_media(),
            ),
            time_estimate=duration_rec + 5,
            progress_display=ProgressDisplay(
                show_bar=True,
                stages=[
                    ProgressStage(3.5, "Wait in silence...", "red"),
                    ProgressStage([3.5, duration_rec - 6], "START TAPPING!", "green"),
                    ProgressStage(3.5, "Stop tapping and wait...", "red", persistent=False),
                    ProgressStage(0.5, "Press Next to continue...", "orange", persistent=True),
                ],
            ),
        )

def welcome():
    return InfoPage(
        Markup("""
        <h3>Welcome</h3>
        <hr>
        In this experiment, you will hear music and be asked to synchronize to the beat by tapping with your finger.
        <br><br>
        Press <b>next</b> when you are ready to start.
        <hr>
        """),
        time_estimate=3
    )

music_tapping = join(
    InfoPage(Markup("""
        <h3>Tapping to Music</h3>
        <hr>
        You will now listen to music.
        <br><br>
        <b>Your goal is to tap in time with the beat of the music until the music ends.</b>
        <br><br>
        There is no metronome. Tap when you feel the beat.
        <hr>
        """), time_estimate=5),
    StaticTrialMaker(
        id_="music_tapping",
        trial_class=TapTrialMusic,
        nodes=nodes_music,
        expected_trials_per_participant=len(nodes_music),
        target_n_participants=NUM_PARTICIPANTS,
        recruit_mode="n_participants",
        check_performance_at_end=False,
    ),
)

class Exp(psynet.experiment.Experiment):
    label = "Beat Finding Experiment"
    asset_storage = LocalStorage()

    config = {
        **get_prolific_settings(),
        "initial_recruitment_size": INITIAL_RECRUITMENT_SIZE,
        "auto_recruit": AUTO_RECRUIT, 
        "title": "Tapping to music (Chrome browser, ~10 mins)",
        "description": "Listen to music and tap along to the beat.",
        "contact_email_on_error": "m.angladatort@gold.ac.uk",
        "organization_name": "Max Planck Institute for Empirical Aesthetics",
        "show_reward": False
    }

    if DEBUG:
        timeline = Timeline(
            NoConsent(),
            welcome(),
            REPPVolumeCalibrationMusic(),
            music_tapping,
            SuccessfulEndPage(),
        )
    else:
        timeline = Timeline(
            NoConsent(),
            welcome(),
            REPPVolumeCalibrationMusic(),
            REPPMarkersTest(),
            REPPTappingCalibration(),
            music_tapping,
            SuccessfulEndPage(),
        )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1
