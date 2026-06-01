import type { ClipDto, ClipUIState, TrackEqState } from "./clip";

// REST API 응답 규격
export interface TrackDto {
    trackId: number; //트랙id
    name: string; //트랙명
    type: string; //트랙타입
    preTrackId: number | null; //이전트랙 id
    postTrackId: number | null; //이후 트랙id
    isMuted: boolean; //음소거 여부
    isSoloed: boolean; // 솔로 활성화 여부
    volume: number; // 트랙의 볼륨(-60~~6dB)
    pan: number; //트랙의 패닝값(-100 ~ 100)
    clips: ClipDto[]; //트랙에 포함된 클립들의 배열
}

//화면 렌더링용 확장 타입
export interface TrackUIState extends TrackDto {
    //?가 있으면 받아올 수도 있고 말수도 있고
    isSelected?: boolean;
    height?: number;
    clips: ClipUIState[]; //클립을 오버라이드
    //왜? 순수 배열 데이터에서 화면을 그리는 상태(선택됨, isSelected)같은 정보를 같이 다루기 위해서
    color?: string;//  트랙별 띠 색
    eq?: TrackEqState;
}
