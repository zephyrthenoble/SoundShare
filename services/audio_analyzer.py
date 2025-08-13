import librosa
import numpy as np
from pathlib import Path
import io
import tempfile
import re
import os
from typing import Dict, List, Tuple, Optional
import soundfile as sf
import traceback

from mutagen import MutagenError

from mutagen import File as MutagenFile

from mutagen.id3 import ID3NoHeaderError
MUTAGEN_AVAILABLE = True

class AudioAnalyzer:
    def __init__(self):
        self.sample_rate = 22050
        
    def analyze_song(self, file_path: str) -> Dict:
        """Analyze a song file and extract mood-related features plus metadata."""
        try:
            # Always extract metadata first (this is more reliable)
            metadata = self.extract_metadata(file_path)
            
            # Try audio analysis, but don't fail if it doesn't work
            try:
                # Load audio file
                y, sr = librosa.load(file_path, sr=self.sample_rate)
                
                # Extract features
                features = {}
                
                # Tempo and beat
                tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
                features['tempo'] = float(tempo)
                
                # Spectral features
                spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
                features['brightness'] = float(np.mean(spectral_centroids))
                
                # MFCC (Mel-frequency cepstral coefficients) for timbre
                mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
                features['mfcc_mean'] = [float(x) for x in np.mean(mfccs, axis=1)]
                
                # Chroma features for key detection
                chroma = librosa.feature.chroma_stft(y=y, sr=sr)
                features['key'] = self._detect_key(chroma)
                
                # Energy and dynamics
                rms = librosa.feature.rms(y=y)[0]
                features['energy'] = float(np.mean(rms))
                features['dynamic_range'] = float(np.std(rms))
                
                # Zero crossing rate (indicates percussive vs. harmonic content)
                zcr = librosa.feature.zero_crossing_rate(y)[0]
                features['zcr'] = float(np.mean(zcr))
                
                # Mood estimation
                mood_features = self._estimate_mood(features)
                features.update(mood_features)
                
                # Combine with metadata
                features.update(metadata)
                
                return features
                
            except Exception as audio_error:
                print(f"Warning: Audio analysis failed for {file_path}: {audio_error}")
                # Return metadata with default audio features
                return {
                    **metadata,
                    'tempo': 120.0,  # Default tempo
                    'energy': 0.5,
                    'valence': 0.5,
                    'danceability': 0.5,
                    'key': 'C',
                    'mode': 'major'
                }
                
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
            # Return minimal metadata even if everything fails
            return self.extract_metadata(file_path)
    
    def extract_metadata(self, file_path: str) -> Dict:
        """Extract metadata from audio file."""
        metadata = {}
        
        try:
            
            try:
                audio_file = MutagenFile(file_path)
                if audio_file is not None:
                    # Extract common tags
                    metadata.update(self._extract_common_tags(audio_file))
                    
                    # Get duration
                    if hasattr(audio_file, 'info') and hasattr(audio_file.info, 'length'):
                        metadata['duration'] = float(audio_file.info.length)
            except MutagenError:
                print(f"Warning: Mutagen failed to read {file_path}: {traceback.format_exc()}")
                # Continue with filename parsing even if mutagen fails
                        
            # Parse filename for track number and clean title
            filename_info = self._parse_filename(file_path)
            metadata.update(filename_info)
            
        except Exception as e:
            print(f"Error extracting metadata from {file_path}: {traceback.format_exc()}")
            # Return basic info from filename even if everything else fails
            metadata = self._parse_filename(file_path)
            
        return metadata
    
    def _extract_common_tags(self, audio_file) -> Dict:
        """Extract common metadata tags from various audio formats."""
        metadata = {}
        
        # Common tag mappings for different formats
        tag_mappings = {
            # musicbrainz
            'title': 'title',
            'artists': 'artist',
            'album': 'album',
            'date': 'year',
            'genre': 'genre',
            'track': 'track',
            'albumartist': 'albumartist',

            # ID3 tags (MP3)
            'TIT2': 'title',
            'TPE1': 'artist', 
            'TALB': 'album',
            'TDRC': 'year',
            'TCON': 'genre',
            'TRCK': 'track',
            'TPE2': 'albumartist',
            
            # Vorbis comments (FLAC, OGG)
            'TITLE': 'title',
            'ARTIST': 'artist',
            'ALBUM': 'album',
            'DATE': 'year',
            'GENRE': 'genre',
            'TRACKNUMBER': 'track',
            'ALBUMARTIST': 'albumartist',
            
            # MP4 tags (M4A)
            '©nam': 'title',
            '©ART': 'artist',
            '©alb': 'album',
            '©day': 'year',
            '©gen': 'genre',
            'trkn': 'track',
            'aART': 'albumartist',
        }
        
        for tag_key, meta_key in tag_mappings.items():
            try:
                if tag_key in audio_file:
                    print(tag_key, meta_key)
                    value = audio_file[tag_key]
                    if isinstance(value, list) and value:
                        value = ", ".join([str(v) for v in value if v])

                    # Special handling for track numbers
                    if meta_key == 'track':
                        if hasattr(value, 'text'):
                            value = value.text[0] if value.text else None
                        if isinstance(value, tuple):
                            value = value[0]  # Get track number from (track, total) tuple
                        if value:
                            try:
                                # Extract just the track number
                                track_str = str(value).split('/')[0]
                                metadata[meta_key] = int(track_str)
                            except (ValueError, IndexError):
                                pass
                    else:
                        # Handle text values
                        if hasattr(value, 'text'):
                            value = value.text[0] if value.text else str(value)
                        
                        metadata[meta_key] = str(value).strip()
            except ValueError:
                pass

        return metadata
    
    def _parse_filename(self, file_path: str) -> Dict:
        """Parse filename for track number and clean display name."""
        from pathlib import Path
        import re
        
        filename = Path(file_path).stem  # Get filename without extension
        metadata = {}
        
        # Common track number patterns at the beginning of filename
        track_patterns = [
            r'^(\d{1,3})\s*[-._\s]+(.+)$',  # "01 - Title", "1. Title", "01_Title"
            r'^(\d{1,3})\s*\.?\s*(.+)$',    # "01 Title", "1.Title"
            r'^Track\s*(\d{1,3})\s*[-._\s]*(.+)$',  # "Track 01 - Title"
        ]
        
        original_title = filename
        track_number = None
        
        for pattern in track_patterns:
            match = re.match(pattern, filename, re.IGNORECASE)
            if match:
                try:
                    track_number = int(match.group(1))
                    cleaned_title = match.group(2).strip()
                    if cleaned_title:  # Only use cleaned title if it's not empty
                        original_title = cleaned_title
                    break
                except (ValueError, IndexError):
                    continue
        
        metadata['parsed_title'] = original_title
        if track_number is not None:
            metadata['parsed_track'] = track_number
        
        return metadata
    
    def _detect_key(self, chroma) -> str:
        """Detect the musical key from chroma features."""
        # Simplified key detection
        key_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        chroma_mean = np.mean(chroma, axis=1)
        key_idx = np.argmax(chroma_mean)
        return key_names[key_idx]
    
    def _estimate_mood(self, features: Dict) -> Dict:
        """Estimate mood-related attributes from audio features."""
        mood = {}
        
        # Energy (0-1 scale)
        # Normalize energy based on typical ranges
        energy = min(1.0, features.get('energy', 0.1) / 0.3)
        mood['energy'] = energy
        
        # Valence (happiness) - based on brightness and tempo
        brightness_norm = min(1.0, features.get('brightness', 1000) / 3000)
        tempo_norm = min(1.0, max(0.0, (features.get('tempo', 120) - 60) / 140))
        valence = (brightness_norm + tempo_norm) / 2
        mood['valence'] = valence
        
        # Danceability - based on tempo and rhythm regularity
        tempo = features.get('tempo', 120)
        if 90 <= tempo <= 140:
            danceability = 0.8
        elif 70 <= tempo <= 160:
            danceability = 0.6
        else:
            danceability = 0.3
        mood['danceability'] = danceability
        
        return mood
    
    def create_preview_segments(self, file_path: str, segment_duration: float = 5.0) -> List[bytes]:
        """Create 5 preview segments of the song as requested."""
        try:
            y, sr = librosa.load(file_path, sr=self.sample_rate)
            duration = len(y) / sr
            segment_samples = int(segment_duration * sr)
            
            segments = []
            
            # 1. Beginning (first 5 seconds)
            start_segment = y[:segment_samples]
            segments.append(self._audio_to_bytes(start_segment, sr))
            
            # 2. Random before middle
            middle_point = len(y) // 2
            before_middle_start = np.random.randint(segment_samples, middle_point - segment_samples)
            before_middle_segment = y[before_middle_start:before_middle_start + segment_samples]
            segments.append(self._audio_to_bytes(before_middle_segment, sr))
            
            # 3. Middle (5 seconds around the center)
            middle_start = middle_point - segment_samples // 2
            middle_segment = y[middle_start:middle_start + segment_samples]
            segments.append(self._audio_to_bytes(middle_segment, sr))
            
            # 4. Random after middle
            after_middle_start = np.random.randint(middle_point, len(y) - segment_samples * 2)
            after_middle_segment = y[after_middle_start:after_middle_start + segment_samples]
            segments.append(self._audio_to_bytes(after_middle_segment, sr))
            
            # 5. End (last 5 seconds)
            end_segment = y[-segment_samples:]
            segments.append(self._audio_to_bytes(end_segment, sr))
            
            return segments
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error creating preview for {file_path}: {e}")
            return []
    
    def _audio_to_bytes(self, audio_data: np.ndarray, sample_rate: int) -> bytes:
        """Convert audio data to bytes for streaming."""
        try:
            # Ensure we have valid audio data
            if len(audio_data) == 0:
                print("Warning: Empty audio data")
                return b''
            
            # Use BytesIO to create WAV data in memory
            with io.BytesIO() as buffer:
                sf.write(buffer, audio_data, int(sample_rate), format='WAV')
                buffer.seek(0)
                data = buffer.getvalue()
                
                if len(data) == 0:
                    print("Warning: Generated zero-length audio data")
                    return b''
                    
                return data
        except Exception as e:
            print(f"Error converting audio to bytes: {e}")
            # Fallback: try with temporary file
            try:
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    sf.write(temp_file.name, audio_data, int(sample_rate))
                    temp_file.close()  # Close the file handle
                    
                    # Read the file content
                    with open(temp_file.name, 'rb') as f:
                        data = f.read()
                    
                    # Clean up the temporary file
                    os.unlink(temp_file.name)
                    
                    if len(data) == 0:
                        print("Warning: Fallback also generated zero-length data")
                        return b''
                        
                    return data
            except Exception as fallback_error:
                print(f"Fallback audio conversion also failed: {fallback_error}")
                return b''
