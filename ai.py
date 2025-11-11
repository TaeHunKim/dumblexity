from google import genai
from google.genai import types
from streamlit_geolocation import streamlit_geolocation
from tavily import TavilyClient
from typing import List, Dict
import re
from youtube_transcript_api import YouTubeTranscriptApi
from pytube import YouTube
import os

available_models = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite", "gemini-2.5-flash-preview-09-2025", "gemini-2.5-flash-lite-preview-09-2025",  "gemini-2.0-flash"]

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

def extract_web_page(urls: List[str]) -> List[Dict[str, str]]:
    """
    Extract raw content from a list of web page URLs.

    Args:
        urls: List of URLs to extract content from.
    Returns:
        List of dictionaries with URL as key and raw content as value.
    """
    tavily_client = TavilyClient(TAVILY_API_KEY)
    response = tavily_client.extract(urls=urls, extract_depth="basic")
    #print(response)
    #return response
    ret = [{x["url"]: x["raw_content"]} for x in response["results"]]
    return ret

def parseYoutubeURL(url:str)->str:
   data = re.findall(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
   if data:
       return data[0]
   return ""

def get_youtube_title(url):
    try:
        yt = YouTube(url)
        return yt.title
    except Exception as e:
        return f"Error: Could not retrieve title. {e}"

def extract_youtube_transcript(video_url: str) -> str:
    """
    Extract transcript from a YouTube video URL.

    Args:
        video_url: URL of the YouTube video.
    Returns:
        Transcript text of the video.
    """
    title = get_youtube_title(video_url)
    video_id = parseYoutubeURL(video_url)
    if not video_id:
        return "Invalid YouTube URL."

    ytt_api = YouTubeTranscriptApi()
    transcript_list = ytt_api.list(video_id)
    try:
        transcript = transcript_list.find_manually_created_transcript(['ko', 'en'])
    except Exception:
        try:
            transcript = transcript_list.find_generated_transcript(['ko', 'en'])
        except Exception:
            return "Transcript not available for this video."
    fetched_transcript = transcript.fetch()
    content = f"Title: {title}\n\n" + "\n".join([x.text for x in fetched_transcript.snippets])
    return content

def generate_config(web_search, map_search, extraction):
    tools = []
    tool_config = None

    if extraction:
        tools.append(extract_youtube_transcript)
        tools.append(extract_web_page)

    if web_search:
        grounding_tool = types.Tool (
            google_search=types.GoogleSearch()
        )
        tools.append(grounding_tool)

    if map_search:
        location = streamlit_geolocation()
        if location:
            latitude = location['latitude']
            longitude = location['longitude']

            map_grounding_tool = types.Tool (
                google_maps=types.GoogleMaps(
                )
            )
            tools.append(map_grounding_tool)

            map_grounding_tool_config = types.ToolConfig(
                retrieval_config = types.RetrievalConfig(
                    lat_lng = types.LatLng( # Pass geo coordinates for location-aware grounding
                        latitude=latitude,
                        longitude=longitude
                    ),
                ),
            )
            tool_config = map_grounding_tool_config

    config = types.GenerateContentConfig(
        tools=tools,
        tool_config=tool_config,
        system_instruction="""
        You are an AI assistant. You can use provided tools for any query that requires up-to-date information or external facts.
        While answering, you can use mermaid diagrams for better explanations when needed, wrapped by ```mermaid\n{diagram}\n```. If adding diagrams, be careful and use escape characters (e.g., double quotes for names/labels).
        """,
        max_output_tokens=65536,
        temperature=0.2,
        thinking_config=types.ThinkingConfig(thinking_budget=-1)
    )
    return config

def get_genai_client():
    return genai.Client()

def genai_stream_wrapper(response_stream, grounding_chunks_list, function_calls_list):
    for chunk in response_stream:
        if chunk.candidates:
            for cand in chunk.candidates:
                if cand.grounding_metadata and cand.grounding_metadata.grounding_chunks:
                    grounding_chunks_list.extend(cand.grounding_metadata.grounding_chunks)
        if chunk.function_calls:
            function_calls_list.extend(chunk.function_calls)
        if chunk.text:
            yield chunk.text

def gen_sdk_history(role, text):
    return types.Content(
        role=role,
        parts=[types.Part(text=text)]
    )

def get_function_call_results(function_calls):
    results = []
    for func_call in function_calls:
        if func_call.name == "extract_web_page":
            result = extract_web_page(func_call.args["urls"])
            results.append(
                types.Part.from_function_response(name=func_call.name, response={"contents":result})
            )
    return results