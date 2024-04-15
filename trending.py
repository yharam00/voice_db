from firebase_admin import firestore
from firebase_admin import storage
import pathlib
import subprocess

import ffmpeg
import streamlit as st
##### 기본 정보 입력 #####
import streamlit as st
# audiorecorder 패키지 추가
from audiorecorder import audiorecorder
# OpenAI 패키기 추가
import openai
# 파일 삭제를 위한 패키지 추가
import os
# 시간 정보를 위핸 패키지 추가
from datetime import datetime
# TTS 패키기 추가
from gtts import gTTS
# 음원파일 재생을 위한 패키지 추가
import base64

##### 기능 구현 함수 #####
def STT(audio, user):
    # 파일 저장
    filename=user+'_'+datetime.now().strftime("%H:%M:%S")+'.mp3'
    audio.export(filename, format="mp3")
    # 음원 파일 열기
    audio_file = open(filename, "rb")
    #Whisper 모델을 활용해 텍스트 얻기
    transcript = openai.Audio.transcribe("whisper-1", audio_file)

    # DB에 저장
    bucket = storage.bucket()
    blob = bucket.blob(filename)
    blob.upload_from_filename(filename)

    audio_file.close()
    # 파일 삭제
    # os.remove(filename)
    return transcript["text"]

def ask_gpt(prompt, model):
    response = openai.ChatCompletion.create(model=model, messages=prompt)
    system_message = response["choices"][0]["message"]
    return system_message["content"]

def TTS(response):
    # gTTS 를 활용하여 음성 파일 생성
    filename = "output.mp3"
    tts = gTTS(text=response,lang="ko")
    tts.save(filename)

    # 음원 파일 자동 재성
    with open(filename, "rb") as f:
        data = f.read()
        b64 = base64.b64encode(data).decode()
        md = f"""
            <audio autoplay="True">
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
            """
        st.markdown(md,unsafe_allow_html=True,)
    # 파일 삭제
    os.remove(filename)

##### 메인 함수 #####
def app():
    if 'db' not in st.session_state:
        st.session_state.db = ''

    db=firestore.client()
    st.session_state.db=db
    

    try:
        # session state 초기화
        if "chat" not in st.session_state:
            st.session_state["chat"] = []

        if "messages" not in st.session_state:
            st.session_state["messages"] = [{"role": "system", "content": "You are a thoughtful assistant. Respond to all input in 25 words and answer in korea"}]

        if "check_reset" not in st.session_state:
            st.session_state["check_reset"] = False

        # 제목 
        st.title(":violet[Voice Chatbot] Baseline Model")
        # 구분선
        st.markdown("---")

        # 기본 설명
        with st.expander("사용하는 법 (클릭하면 닫을 수 있습니다)", expanded=True):
            st.write(
            """     
            - 먼저, 좌측 상단 사이드바를 열어 OpenAI API 키를 입력해 주세요.
            - 다음으로 답변 생성에 사용될 GPT 모델을 설정해 주세요.
            - 초기화 버튼을 누르면 이전 대화 내용이 리셋됩니다.
            - 이제 사이드바를 닫고, 클릭하여 녹음하기 버튼을 눌러 챗봇에게 질문하세요.
            - 질문이 끝나면 녹음중... 버튼을 눌러 녹음을 종료하세요
            - 질문에 대한 답변이 음성으로 출력되고 채팅 내용이 오른쪽에 표시됩니다.
            - 방금 내가 질문한 내용은 왼쪽 하단에서 들어볼 수 있습니다.
            """
            )

            st.markdown("")

        # 사이드바 생성
        with st.sidebar:

            # Open AI API 키 입력받기
            openai.api_key = st.text_input(label="OPENAI API 키", placeholder="Enter Your API Key", type="password")

            st.markdown("---")

            # GPT 모델을 선택하기 위한 라디오 버튼 생성
            model = st.radio(label="GPT 모델",options=["gpt-4", "gpt-3.5-turbo"])

            st.markdown("---")

            # 리셋 버튼 생성
            if st.button(label="초기화"):
                # 리셋 코드 
                st.session_state["chat"] = []
                st.session_state["messages"] = [{"role": "system", "content": "You are a thoughtful assistant. Respond to all input in 25 words and answer in korea"}]
                st.session_state["check_reset"] = True
                
        # 기능 구현 공간
        col1, col2 =  st.columns(2)
        with col1:
            # 왼쪽 영역 작성
            st.subheader("질문하기")
            # 음성 녹음 아이콘 추가
            audio = audiorecorder("클릭하여 녹음하기", "녹음중...")
            if (audio.duration_seconds > 0) and (st.session_state["check_reset"]==False):
                # 음성 재생 
                st.audio(audio.export().read())
                # 음원 파일에서 텍스트 추출
                question = STT(audio, st.session_state.username)

                # 채팅을 시각화하기 위해 질문 내용 저장
                now = datetime.now().strftime("%H:%M")
                st.session_state["chat"] = st.session_state["chat"]+ [("user",now, question)]
                # GPT 모델에 넣을 프롬프트를 위해 질문 내용 저장
                st.session_state["messages"] = st.session_state["messages"]+ [{"role": "user", "content": question}]

                # DB에 질문 내용 저장
                info = db.collection('Chat').document(st.session_state.username).get()
                if info.exists:
                    info = info.to_dict()
                    if 'Content' in info.keys():
                        pos=db.collection('Chat').document(st.session_state.username)
                        pos.update({u'Content': firestore.ArrayUnion([u'{}'.format(question)])})
                    else:
                        data={"Content":[question],'Username':st.session_state.username}
                        db.collection('Chat').document(st.session_state.username).set(data)
                else:
                    data={"Content":[question],'Username':st.session_state.username}
                    db.collection('Chat').document(st.session_state.username).set(data)

        with col2:
            # 오른쪽 영역 작성
            st.subheader("질문/답변")
            if  (audio.duration_seconds > 0)  and (st.session_state["check_reset"]==False):
                #ChatGPT에게 답변 얻기
                response = ask_gpt(st.session_state["messages"], model)

                # GPT 모델에 넣을 프롬프트를 위해 답변 내용 저장
                st.session_state["messages"] = st.session_state["messages"]+ [{"role": "system", "content": response}]

                # 채팅 시각화를 위한 답변 내용 저장
                now = datetime.now().strftime("%H:%M")
                st.session_state["chat"] = st.session_state["chat"]+ [("bot",now, response)]

                # 채팅 형식으로 시각화 하기
                for sender, time, message in st.session_state["chat"]:
                    if sender == "user":
                        st.write(f'<div style="display:flex;align-items:center;"><div style="background-color:#007AFF;color:white;border-radius:12px;padding:8px 12px;margin-right:8px;">{message}</div><div style="font-size:0.8rem;color:gray;">{time}</div></div>', unsafe_allow_html=True)
                        st.write("")
                    else:
                        st.write(f'<div style="display:flex;align-items:center;justify-content:flex-end;"><div style="background-color:lightgray;border-radius:12px;padding:8px 12px;margin-left:8px;">{message}</div><div style="font-size:0.8rem;color:gray;">{time}</div></div>', unsafe_allow_html=True)
                        st.write("")
                
                # gTTS 를 활용하여 음성 파일 생성 및 재생
                TTS(response)
            else:
                st.session_state["check_reset"] = False
    except:
        if st.session_state.username=='':
            st.success('Please Login first')
        else:
            st.success('Check API Key')