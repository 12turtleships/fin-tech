import os

from youtube_transcript_api import YouTubeTranscriptApi

video_id = "3XbtEX3jUv4"
ytt_api = YouTubeTranscriptApi()

# Fetch transcript - tries English first, then Korean if English is not available
# The fetch method accepts 'languages' parameter (not 'language_codes')
transcript = ytt_api.fetch(video_id, languages=['en', 'ko'])

# Extract text only from all snippets and merge them
text_only = ' '.join([snippet.text for snippet in transcript.snippets])
print(text_only)