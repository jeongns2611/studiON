//진입점 파일
//프로그램이 시작되면 가장 먼저 읽는 파일
//여기서 전역 설정(언어, 라우터, 상태관리 등)을 하고 앱을 시작함
//vue의 핵심 기능인 createApp을 가져와서 앱을 생성하고 #app에 마운트(연결)함
import { createApp } from 'vue'
//디자인 가져오기
import './style.css'
import App from './app/App.vue'
import router from './app/router'
//Pinia 상태관리 설정
import { createPinia } from 'pinia'
//복구플러그인(새로고침해도 유지)
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'

const app = createApp(App)
const pinia = createPinia() //피니아 인스턴스를 생성
pinia.use(piniaPluginPersistedstate) //복구플러그인 적용

//순서 중요
app.use(pinia) //피니아 먼저 설치
app.use(router) //그 다음 라우터 설치
app.mount('#app') //마지막으로 마운트
//파일은 @/app/App.vue를 화면에 띄우고, 라우터와 피니아가 연결된 앱을 실행시킴
