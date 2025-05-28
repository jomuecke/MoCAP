import streamlit as st
import ffmpeg
import tempfile
import os

st.set_page_config(layout="wide")
st.title("🎞️ Video Viewer (H.264 & MP4)")

st.markdown("Upload two `.mp4` or `.h264` videos. H.264 files will be converted to MP4 automatically.")

def convert_h264_to_mp4(h264_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".h264") as temp_input:
        temp_input.write(h264_file.read())
        temp_input_path = temp_input.name

    temp_output = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    temp_output_path = temp_output.name
    temp_output.close()

    try:
        ffmpeg.input(temp_input_path, framerate=30).output(temp_output_path, vcodec='libx264').run(overwrite_output=True, quiet=True)
        return temp_output_path
    except ffmpeg.Error as e:
        st.error(f"FFmpeg conversion failed: {e.stderr.decode()}")
        return None
    finally:
        os.remove(temp_input_path)

def load_video(uploaded_file):
    if uploaded_file is None:
        return None

    if uploaded_file.name.endswith(".mp4"):
        return uploaded_file
    elif uploaded_file.name.endswith(".h264"):
        mp4_path = convert_h264_to_mp4(uploaded_file)
        if mp4_path:
            return open(mp4_path, "rb")
    else:
        st.warning("Unsupported file format.")
        return None

col1, col2 = st.columns(2)

with col1:
    uploaded1 = st.file_uploader("Upload First Video (.mp4 or .h264)", type=["mp4", "h264"], key="vid1")
    video1 = load_video(uploaded1)
    if video1:
        st.video(video1)

with col2:
    uploaded2 = st.file_uploader("Upload Second Video (.mp4 or .h264)", type=["mp4", "h264"], key="vid2")
    video2 = load_video(uploaded2)
    if video2:
        st.video(video2)
