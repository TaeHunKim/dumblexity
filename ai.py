from google import genai
from google.genai import types
from streamlit_geolocation import streamlit_geolocation
from tavily import TavilyClient
from typing import List, Dict, Union, Any
import re
from youtube_transcript_api import YouTubeTranscriptApi
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
#from pytube import YouTube
import os

available_models = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite", "gemini-2.5-flash-preview-09-2025", "gemini-2.5-flash-lite-preview-09-2025",  "gemini-2.0-flash"]

YOUTUBE_DATA_API_KEY = os.getenv("YOUTUBE_DATA_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
# GEMINI_API_KEY is used internally by genai library so need to set in env variable

def search_web_tavily(query: str, topic: str = "general", time_range: str = None, start_date: str = None, end_date: str = None, max_results: int = 5,
                      include_answer: Union[bool, str] = False, include_raw_content: Union[bool, str] = False, country: str = None) -> Dict[str, Any]:
    """
    Perform a web search using Tavily API.

    Args:
        query: The search query string. It can be a natural language question (e.g., Who is Leo Messi?)
        topic: The topic category for the search. One of "general", "news", and "finance". Default is "general".
        time_range: The time range back from the current date based on publish date or last updated date. Accepted values include "day", "week", "month", "year" or shorthand values "d", "w", "m", "y". Default is None (no time filter).
        start_date: The start date (YYYY-MM-DD) to filter search results based on publish or last update. Default is None.
        end_date: The end date (YYYY-MM-DD) to filter search results based on publish or last update. Default is None.
        max_results: Maximum number of search results to return. Default is 5.
        include_answer: Whether to include summarized answers. "basic" or True is quick but less detailed. "advanced" is slower but more comprehensive. Default is False.
        include_raw_content: Whether to include raw content from web pages. "markdown" or True returns search result content in markdown format. "text" returns the plain text from the results and may increase latency. Default is False.
        country: Country name or 2-letter country code to localize search results (e.g., "United States" or "US"). Available only if topic is "general". Default is None.
    Returns:
        Dictionary containing search results.
    """
    #print(f"Searching Tavily for query: {query}")
    tavily_client = TavilyClient(TAVILY_API_KEY)
    response = tavily_client.search(
        query=query,
        auto_parameters=False,
        topic=topic,
        time_range=time_range,
        start_date=start_date,
        end_date=end_date,
        max_results=max_results,
        include_answer=include_answer,
        include_raw_content=include_raw_content,
        country=country
    )
    #print(f"Tavily search response: {response}")
    return response 

def extract_web_page(urls: List[str]) -> List[Dict[str, str]]:
    """
    Extract raw content from a list of web page URLs.

    Args:
        urls: List of URLs to extract content from.
    Returns:
        List of dictionaries with URL as key and raw content as value.
    """
    tavily_client = TavilyClient(TAVILY_API_KEY)
    response = tavily_client.extract(urls=urls, extract_depth="advanced")
    #print(response)
    #return response
    ret = [{'url': x["url"], 'content': x["raw_content"]} for x in response["results"]]
    return ret

def _parse_youtube_url(url:str)->str:
    """
    YouTube URL에서 비디오 ID를 추출합니다.
    (표준, 단축, 임베드 URL 등 다양한 형식을 지원)
    """
    patterns = [
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})',
        r'(?:https?:\/\/)?(?:www\.)?youtu\.be\/([a-zA-Z0-9_-]{11})',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def _get_youtube_details(video_id):
    """
    YouTube Data API v3를 사용해 비디오의 제목과 설명을 가져옵니다.
    """
    try:
        api_key = YOUTUBE_DATA_API_KEY
        # YouTube API 서비스 빌드
        youtube = build('youtube', 'v3', developerKey=api_key)
        
        request = youtube.videos().list(
            part="snippet", # 'snippet' 부분에 제목, 설명이 포함됨
            id=video_id
        )
        response = request.execute()
        
        if not response.get('items'):
            print(f"오류: 비디오 ID '{video_id}'를 찾을 수 없습니다.")
            return None, None
            
        snippet = response['items'][0]['snippet']
        title = snippet.get('title', 'No title')
        description = snippet.get('description', 'No description')
        
        return title, description

    except HttpError as e:
        print(f"API 호출 중 오류 발생: {e}")
        return None, None
    except Exception as e:
        print(f"알 수 없는 오류 발생 (get_video_details): {e}")
        return None, None

def extract_youtube_transcript(video_url: str) -> str:
    """
    Extract transcript from a YouTube video URL.
    Note: Transcript may generated automatically and accuracy is not guaranteed. You can refer title and description of the video for more context and better accuracy.

    Args:
        video_url: URL of the YouTube video.
    Returns:
        Transcript text of the video.
    """
    video_id = _parse_youtube_url(video_url)
    if not video_id:
        return "Invalid YouTube URL."
    title, description = _get_youtube_details(video_id)

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
    content = "\n".join([x.text for x in fetched_transcript.snippets])
    return [{'url': video_url, 'title': title, 'description': description, 'content': content}]

def generate_config(google_web_search, google_map_search, tavily_search, extraction):
    tools = []
    tool_config = None

    if tavily_search:
        tools.append(search_web_tavily)

    if extraction:
        tools.append(extract_youtube_transcript)
        tools.append(extract_web_page)

    if google_web_search:
        grounding_tool = types.Tool (
            google_search=types.GoogleSearch()
        )
        tools.append(grounding_tool)

    if google_map_search:
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
        * While answering, you can use mermaid diagrams for better explanations when needed, wrapped by ```mermaid\n{diagram}\n```.
            * If adding diagrams, do not forget to wrap text in each box with double quotes. e.g., A["This is a box"]
        * If you search the web and user's question includes relative time references like "recently" or "now", do not fix the search query with the date you know.
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
        if chunk.automatic_function_calling_history:
            function_calls_list.extend(chunk.automatic_function_calling_history)
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