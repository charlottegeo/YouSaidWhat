import binascii
from flask import Flask, request, render_template, jsonify
import numpy as np
import whisper
from pydub import AudioSegment
from io import BytesIO
from flask_socketio import SocketIO, emit
import base64
import webrtcvad
import torch

SAMPLE_RATE = 16000  # 16 kHz
SAMPLE_WIDTH = 2  # 16 bits = 2 bytes
CHANNELS = 1  # Mono audio
DURATION_THRESHOLD = 0.5  # seconds
BUFFER_THRESHOLD = int(SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS * DURATION_THRESHOLD)
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)
vad = webrtcvad.Vad(1)

model = whisper.load_model("base")

audio_buffer = bytearray()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/transcribe', methods=['POST'])
def transcribe():
    if 'audio_data' not in request.files:
        return "Audio data not found", 400
    
    audio_file = request.files['audio_data']
    audio_content = audio_file.read()
    
    audio = AudioSegment.from_file(BytesIO(audio_content), format="ogg")
    audio = audio.set_channels(1)
    audio = audio.set_frame_rate(16000)
    
    raw_audio_data = audio.raw_data
    
    audio_data = np.frombuffer(raw_audio_data, dtype=np.int16).astype(np.float32) / 32768.0
    
    result = model.transcribe(audio_data, fp16=torch.cuda.is_available())
    text = result['text'].strip()

    return jsonify({'transcription': text})

def transcribe_audio(chunk):
    sample_width = 2
    channels = 1  # Mono audio
    frame_rate = 16000  # Target frame rate
    
    # Ensure the chunk is padded correctly to match frame_size
    frame_size = sample_width * channels
    remainder = len(chunk) % frame_size
    if remainder != 0:
        padding = frame_size - remainder
        chunk += bytes([0] * padding)  # Pad with zeroes
    
    try:
        audio_segment = AudioSegment(
            data=chunk,
            sample_width=SAMPLE_WIDTH,
            frame_rate=SAMPLE_RATE,
            channels=CHANNELS
        )
    except ValueError as e:
        print(f"Error creating audio segment: {e}")
        return ""

    audio_np = np.array(audio_segment.get_array_of_samples()).astype(np.float32) / 32768.0
    
    result = model.transcribe(audio_np)
    text = result['text'].strip()
    print(f"Transcribed Text: {text}")
    
    return text



@socketio.on('audio_chunk')
def handle_audio_chunk(data):
    global audio_buffer
    if isinstance(data, str):
        data += "=" * ((4 - len(data) % 4) % 4)
        try:
            audio_chunk = base64.b64decode(data)
            audio_buffer.extend(audio_chunk)
            
            while len(audio_buffer) >= BUFFER_THRESHOLD:
                chunk_to_process = audio_buffer[:BUFFER_THRESHOLD]
                text = transcribe_audio(chunk_to_process)
                print(f"Transcribed Text: {text}")
                emit('transcription', {'text': text})
                
                audio_buffer = audio_buffer[BUFFER_THRESHOLD:]
                
        except binascii.Error as e:
            print(f"Error decoding base64: {e}")

if __name__ == '__main__':
    socketio.run(app, debug=True)