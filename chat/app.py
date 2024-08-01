import logging
import os
import sqlite3
import uuid
from io import BytesIO

import chainlit as cl
import config

import speech_recognition as sr
import whisper
from chainlit.element import ElementBased
from gtts import gTTS
from langchain.schema.runnable import Runnable
from langchain.schema.runnable.config import RunnableConfig
from logs import configure_logging
from pydub import AudioSegment
from pydub.utils import which
from rag import Rag

whisper_model = whisper.load_model("base")
AudioSegment.converter = which("ffmpeg")
temp_audio_path = "temp_audio.wav"

async def save_chat(conversation_id, message_content, role):
    try:
        con = sqlite3.connect(config.database_path + "/database.db")
        cur = con.cursor()
        cur.execute(
            "INSERT INTO chat_history (conversation_id, message_content, role) VALUES (?, ?, ?);",
            (conversation_id, message_content, role),
        )
        con.commit()
        cur.close()  
    except sqlite3.Error as e:
        logging.error(f"An error occurred: {e}")
    finally:
        con.close()


@cl.step(type="tool")
async def speech_to_text(audio_file):
    recognizer = sr.Recognizer()
    audio = BytesIO(audio_file)
    
    
    try:
      
       
        audio.seek(0)
        audio_segment = AudioSegment.from_file(audio)
        audio_segment.export(temp_audio_path, format="wav")

        audio_data = sr.AudioFile(temp_audio_path)
        with audio_data as source:
            audio_data = recognizer.record(source)

        result = whisper_model.transcribe(temp_audio_path, fp16=False)
        print(result)

        

        return result["text"]
    except sr.UnknownValueError:
        return "Sorry, I could not understand the audio."
    except sr.RequestError as e:
        return f"Could not request results from Google Speech Recognition service; {e}"
    except Exception as e:
        return f"An error occurred while processing the audio: {e}"
    # finally:
    #     if os.path.exists(temp_audio_path):
    #         os.remove(temp_audio_path)


@cl.step(type="tool")
async def text_to_speech(text: str, mime_type: str):
    tts = gTTS(text)
    output_buffer = BytesIO()
    tts.save("output_audio.mp3")

    audio = AudioSegment.from_file("output_audio.mp3")
    output_buffer = BytesIO()
    audio.export(output_buffer, format=mime_type.split("/")[1])
    output_buffer.seek(0)

    os.remove("output_audio.mp3")

    return "output_audio.mp3", output_buffer.read()


@cl.on_chat_start
async def start():
    configure_logging()
    try:
        cl.user_session.set("chain", Rag().chain)
        cl.user_session.set("chat_history", "")
        conversation_id = str(uuid.uuid4())
        cl.user_session.set("conversation_id", conversation_id)
        system_prompt = config.base_prompt + config.custom_prompt
        logging.info(f"System: {system_prompt}")
        await save_chat(conversation_id, system_prompt, "system")
    except Exception as e:
        logging.error(f"Error during chat start: {e}")


@cl.on_audio_chunk
async def on_audio_chunk(chunk: cl.AudioChunk):
    if chunk.isStart:
        buffer = BytesIO()
        buffer.name = f"input_audio.{chunk.mimeType.split('/')[1]}"
        cl.user_session.set("audio_buffer", buffer)
        cl.user_session.set("audio_mime_type", chunk.mimeType)

    cl.user_session.get("audio_buffer").write(chunk.data)


@cl.on_audio_end
async def on_audio_end(elements: list[ElementBased]):
    chain = cl.user_session.get("chain")
    chat_history = cl.user_session.get("chat_history")
    audio_buffer: BytesIO = cl.user_session.get("audio_buffer")
    audio_buffer.seek(0)
    audio_file = audio_buffer.read()
    audio_mime_type: str = cl.user_session.get("audio_mime_type")
    res = ""
    transcription = await speech_to_text(audio_file)
    await cl.Message(author="You", type="user_message", content=transcription).send()
    if os.path.exists(temp_audio_path):
        os.remove(temp_audio_path)
    msg = await cl.Message(content="").send()
    
    async for chunk in chain.astream(
        {
            "chat_history": chat_history,
            "question": transcription,
        },
        config=RunnableConfig(callbacks=[cl.LangchainCallbackHandler()]),
    ):
        await msg.stream_token(chunk)
        res += chunk
    await msg.send()
    logging.info(f"AI: {res}")
    output_name, output_audio = await text_to_speech(res, audio_mime_type)
    output_audio_el = cl.Audio(
        name=output_name,
        auto_play=True,
        mime=audio_mime_type,
        content=output_audio,
    )
    chat_history += f"Human: {transcription}\nAI: {res}\n"
    cl.user_session.set("chat_history", chat_history)
    msg.elements = [output_audio_el]
    await msg.update()
    conversation_id = cl.user_session.get("conversation_id")
    await save_chat(conversation_id, transcription, "user")
    await save_chat(conversation_id, res, "assistant")
    cl.user_session.set("audio_buffer", None)
    cl.user_session.set("audio_mime_type", None)


@cl.on_message
async def main(message):
    chain = cl.user_session.get("chain")
    chat_history = cl.user_session.get("chat_history")
    res = ""
    message_content = message.content.strip().lower()
    logging.info(f"User: {message_content}")
    msg = cl.Message(content="")
    async for chunk in chain.astream(
        {
            "chat_history": chat_history,
            "question": message_content,
        },
        config=RunnableConfig(callbacks=[cl.LangchainCallbackHandler()]),
    ):
        await msg.stream_token(chunk)
        res += chunk
    await msg.send()
    logging.info(f"AI: {res}")

    chat_history += f"Human: {message_content}\nAI: {res}\n"
    cl.user_session.set("chat_history", chat_history)
    conversation_id = cl.user_session.get("conversation_id")
    await save_chat(conversation_id, message_content, "user")
    await save_chat(conversation_id, res, "assistant")