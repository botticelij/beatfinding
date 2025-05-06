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
        "currency": "£",
        "wage_per_hour": 0.01
    }

DEBUG = True
RECRUITER = "prolific"
INITIAL_RECRUITMENT_SIZE = 10
AUTO_RECRUIT = False
NUM_PARTICIPANTS = 20
DURATION_ESTIMATED_TRIAL = 40

music_stimulus_name = ["music1psynet", "music2psynet", "music3psynet", "music4psynet"]
music_stimulus_audio = ["music/music1psynet.wav", "music/music2psynet.wav", "music/music3psynet.wav", "music/music4psynet.wav"]

practice_stimulus_name = ["music_practice1", "music_practice2"]
practice_stimulus_audio = ["music/music_practice1.wav", "music/music_practice2.wav"]

@cache
def create_music_stim_with_repp(stim_name, audio_filename):
    stimulus = REPPStimulus(stim_name, config=sms_tapping)
    stim_prepared, stim_info, _ = stimulus.prepare_stim_from_files("music")
    info = json.dumps(stim_info, cls=NumpySerializer)  # store as JSON string
    return stim_prepared, info

def generate_music_stimulus_audio(path, stim_name, audio_filename):
    stim_prepared, _ = create_music_stim_with_repp(stim_name, audio_filename)
    save_samples_to_file(stim_prepared, path, sms_tapping.FS)

def generate_music_stimulus_info(path, stim_name, audio_filename):
    _, info = create_music_stim_with_repp(stim_name, audio_filename)
    save_json_to_file(info, path)

def make_nodes(names, audios):
    return [
        StaticNode(
            definition={"stim_name": name, "audio_filename": audio},
            assets={
                "stimulus_audio": CachedFunctionAsset(generate_music_stimulus_audio),
                "stimulus_info": CachedFunctionAsset(generate_music_stimulus_info),
            },
        )
        for name, audio in zip(names, audios)
    ]

nodes_music = make_nodes(music_stimulus_name, music_stimulus_audio)
nodes_practice = make_nodes(practice_stimulus_name, practice_stimulus_audio)

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

        try:
            analysis = REPPAnalysis(config=sms_tapping)
            output, analysis_data, is_failed = analysis.do_analysis(
                stim_info=info,
                recording_filename=audio_file,
                title_plot=title_in_graph,
                output_plot=output_plot,
            )
            return {
                "failed": is_failed.get("failed", False),
                "reason": is_failed.get("reason", None),
                "output": json.dumps(output, cls=NumpySerializer),
                "analysis": json.dumps(analysis_data, cls=NumpySerializer),
                "stim_name": stim_name,
            }
        except Exception as e:
            return {
                "failed": True,
                "reason": f"analysis_exception: {str(e)}",
                "output": None,
                "analysis": None,
                "stim_name": stim_name,
            }

class TapTrialMusic(TapTrialAnalysis):
    time_estimate = DURATION_ESTIMATED_TRIAL

    def get_bot_response_media(self):
        return {
            "music1psynet": "example_music_tapping_track_1.wav",
            "music2psynet": "example_music_tapping_track_2.wav",
            "music3psynet": "example_music_tapping_track_1.wav",
            "music4psynet": "example_music_tapping_track_2.wav",
            "music_practice1": "example_music_tapping_track_1.wav",
            "music_practice2": "example_music_tapping_track_2.wav",
        }[self.definition["stim_name"]]

    def show_trial(self, experiment, participant):
        info = self.get_info()
        duration_rec = info.get("stim_duration", 30)
        stim_name = self.definition["stim_name"]
        is_practice = stim_name.startswith("music_practice")
        trial_number = self.position + 1
        trial_label = f"Practice Trial {trial_number}" if is_practice else f"Trial {trial_number}"

        instructions = (
            "<p>This is a <b>practice</b> trial to help you get used to the task.</p>"
            if is_practice else
            "<p>Listen carefully to the music and <b>tap in time with the beat you hear</b>, as naturally as you would tap your foot or nod your head along with music.</p>"
        )

        return ModularPage(
            "trial_main_page",
            AudioPrompt(
                self.assets["stimulus_audio"].url,
                Markup(
                    f"""
                    <h3>{trial_label}</h3>
                    {instructions}
                    <p><i>Do not tap on the keyboard or trackpad — use your index finger on the surface of your laptop.</i></p>
                    <p>Try to be as consistent and accurate as possible.</p>
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
        Markup("""<h2>Welcome to the Beat Perception Experiment</h2><hr>
        <p>In this study, you will listen to short excerpts of music and tap <b>in time with the beat you perceive</b> — like tapping your foot to music.</p>
        <p><b>Use your index finger to tap on the surface of your laptop (not the keys or trackpad).</b></p>
        <p>There is no metronome — you should tap to the beat that feels natural to you.</p>
        <p>Make sure your <b>volume is up</b> and <b>headphones are unplugged</b>.</p>
        <p>The experiment should take around 10 minutes.</p><hr>
        <p>Press <b>Next</b> when you're ready to begin.</p>"""),
        time_estimate=5
    )

music_tapping_practice = StaticTrialMaker(
    id_="music_tapping_practice",
    trial_class=TapTrialMusic,
    nodes=nodes_practice,
    expected_trials_per_participant=len(nodes_practice),
    target_n_participants=NUM_PARTICIPANTS,
    recruit_mode="n_participants",
    check_performance_at_end=False,
)

music_tapping = StaticTrialMaker(
    id_="music_tapping",
    trial_class=TapTrialMusic,
    nodes=nodes_music,
    expected_trials_per_participant=len(nodes_music),
    target_n_participants=NUM_PARTICIPANTS,
    recruit_mode="n_participants",
    check_performance_at_end=False,
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
        "show_reward": False,
    }

    if DEBUG:
        timeline = Timeline(
            NoConsent(),
            welcome(),
            REPPVolumeCalibrationMusic(),
            music_tapping_practice,
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
            music_tapping_practice,
            music_tapping,
            SuccessfulEndPage(),
        )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1
