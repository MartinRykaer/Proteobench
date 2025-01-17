"""Streamlit-based web interface for ProteoBench."""

import json
import logging
from datetime import datetime

from proteobench.modules.dda_quant.module import Module
from proteobench.modules.dda_quant.parse_settings import INPUT_FORMATS
from proteobench.modules.dda_quant.plot import PlotDataPoint

try:
    from importlib.metadata import version
except ImportError:
    from importlib_metadata import version

import streamlit as st
from streamlit_extras.let_it_rain import rain
from streamlit_utils import hide_streamlit_menu, save_dataframe

from proteobench.github.gh import clone_pr

logger = logging.getLogger(__name__)

ALL_DATAPOINTS = "all_datapoints"
SUBMIT = "submit"
FIG1 = "fig1"
FIG2 = "fig2"
RESULT_PERF = "result_perf"

if "submission_ready" not in st.session_state:
    st.session_state["submission_ready"] = False


class StreamlitUI:
    """Proteobench Streamlit UI."""

    def __init__(self):
        """Proteobench Streamlit UI."""
        self.texts = WebpageTexts
        self.user_input = dict()

        st.set_page_config(
            page_title="Proteobench web server",
            page_icon=":rocket:",
            layout="centered",
            initial_sidebar_state="expanded",
        )
        if SUBMIT not in st.session_state:
            st.session_state[SUBMIT] = False
        self._main_page()
        self._sidebar()

    def generate_input_field(self, input_format: str, content: dict):
        if content["type"] == "text_input":
            return st.text_input(content["label"], content["value"][input_format])
        if content["type"] == "number_input":
            return st.number_input(
                content["label"],
                value=content["value"][input_format],
                format=content["format"],
            )
        if content["type"] == "selectbox":
            return st.selectbox(
                content["label"],
                content["options"],
                content["options"].index(content["value"][input_format]),
            )
        if content["type"] == "checkbox":
            return st.checkbox(content["label"], content["value"][input_format])

    def _main_page(self):
        """Format main page."""
        st.title("Proteobench")
        st.header("Input and configuration")

        with st.form(key="main_form"):
            st.subheader("Input files")
            self.user_input["input_csv"] = st.file_uploader(
                "Search engine result file", help=self.texts.Help.input_file
            )

            self.user_input["input_format"] = st.selectbox(
                "Search engine", INPUT_FORMATS
            )

            # self.user_input["pull_req"] = st.text_input(
            #     "Open pull request to make results available to everyone (type \"YES\" to enable)",
            #     "NO"
            # )

            with st.expander("Additional parameters"):

                with open("webinterface/configuration/dda_quant.json") as file:
                    config = json.load(file)

                for key, value in config.items():
                    self.user_input[key] = self.generate_input_field(
                        self.user_input["input_format"], value
                    )

            submit_button = st.form_submit_button("Parse and bench")

        # if st.session_state[SUBMIT]:
        if FIG1 in st.session_state:
            self._populate_results()

        if submit_button:
            self._run_proteobench()

    def _populate_results(self):
        self.generate_results("", None, None, False)

    def _sidebar(self):
        """Format sidebar."""
        st.sidebar.image(
            "https://upload.wikimedia.org/wikipedia/commons/8/85/Garden_bench_001.jpg",
            width=150,
        )
        # st.sidebar.markdown(self.texts.Sidebar.badges)
        st.sidebar.header("About")
        st.sidebar.markdown(self.texts.Sidebar.about, unsafe_allow_html=True)

    def _run_proteobench(self):
        # Run Proteobench
        st.header("Running Proteobench")
        status_placeholder = st.empty()
        status_placeholder.info(":hourglass_flowing_sand: Running Proteobench...")

        if ALL_DATAPOINTS not in st.session_state:
            st.session_state[ALL_DATAPOINTS] = None

        try:
            result_performance, all_datapoints = Module().benchmarking(
                self.user_input["input_csv"],
                self.user_input["input_format"],
                self.user_input,
                st.session_state["all_datapoints"],
            )
            st.session_state[ALL_DATAPOINTS] = all_datapoints
        except Exception as e:
            status_placeholder.error(":x: Proteobench ran into a problem")
            st.exception(e)
        else:
            self.generate_results(
                status_placeholder, result_performance, all_datapoints, True
            )

    def generate_results(
        self, status_placeholder, result_performance, all_datapoints, recalculate
    ):
        time_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if recalculate:
            status_placeholder.success(":heavy_check_mark: Finished!")

            # Show head of result DataFrame
        st.header("Results")
        st.subheader("Sample of the processed file")
        if not recalculate:
            result_performance = st.session_state[RESULT_PERF]
            all_datapoints = st.session_state[ALL_DATAPOINTS]
        st.dataframe(result_performance.head(100))

        # Plot results
        st.subheader("Ratio between conditions")
        if recalculate:
            fig = PlotDataPoint().plot_bench(result_performance)
        else:
            fig = st.session_state[FIG1]
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Mean error between conditions")
        # show metadata
        # st.text(all_datapoints.head(100))

        if recalculate:
            fig2 = PlotDataPoint().plot_metric(all_datapoints)
        else:
            fig2 = st.session_state[FIG2]
        st.plotly_chart(fig2, use_container_width=True)

        sample_name = "%s-%s-%s-%s" % (
            self.user_input["input_format"],
            self.user_input["version"],
            self.user_input["mbr"],
            time_stamp,
        )

        # Download link
        st.subheader("Download calculated ratios")
        st.download_button(
            label="Download",
            data=save_dataframe(result_performance),
            file_name=f"{sample_name}.csv",
            mime="text/csv",
        )

        st.subheader("Add results to online repository")
        st.session_state[FIG1] = fig
        st.session_state[FIG2] = fig2
        st.session_state[RESULT_PERF] = result_performance
        st.session_state[ALL_DATAPOINTS] = all_datapoints

        checkbox = st.checkbox("I confirm that the metadata is correct")
        if checkbox:
            st.session_state["submission_ready"] = True
            submit_pr = st.button("I really want to upload it")
            # TODO: check if parameters are filled
            # submit_pr = False
            if submit_pr:
                st.session_state[SUBMIT] = True
                clone_pr(
                    st.session_state[ALL_DATAPOINTS],
                    st.secrets["gh"]["token"],
                    username="Proteobot",
                    remote_git="github.com/Proteobot/Results_Module2_quant_DDA.git",
                    branch_name="new_branch",
                )
        if SUBMIT in st.session_state:
            if st.session_state[SUBMIT]:
                # status_placeholder.success(":heavy_check_mark: Successfully uploaded data!")
                st.subheader("SUCCESS")
                st.session_state[SUBMIT] = False
                rain(emoji="🎈", font_size=54, falling_speed=5, animation_length=1)


class WebpageTexts:
    class Sidebar:

        about = f"""
            """

    class Help:
        input_file = """
            Output file of the search engine
            """

        pull_req = """
            It is open to the public indefinitely.
            """

    class Errors:
        missing_peptide_csv = """
            Upload a peptide CSV file or select the _Use example data_ checkbox.
            """
        missing_calibration_peptide_csv = """
            Upload a calibration peptide CSV file or select another _Calibration
            peptides_ option.
            """
        missing_calibration_column = """
            Upload a peptide CSV file with a `tr` column or select another _Calibration
            peptides_ option.
            """
        invalid_peptide_csv = """
            Uploaded peptide CSV file could not be read. Click on _Info about peptide
            CSV formatting_ for more info on the correct input format.
            """
        invalid_calibration_peptide_csv = """
            Uploaded calibration peptide CSV file could not be read. Click on _Info
            about peptide CSV formatting_ for more info on the correct input format.
            """


if __name__ == "__main__":
    StreamlitUI()
