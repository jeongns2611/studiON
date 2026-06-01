/// <reference types="vite/client" />
// .vue파일들에 대해서 에러내지 말고 Vue 컴포넌트라고 인식
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, any>;
  export default component
}