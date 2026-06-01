package com.salmon.studion.global.common.enums;

public enum ProjectWebSocketEventType {

    PROJECT_ONLINE_USERS,   // 프로젝트 내 접속자 목록

    PROJECT_JOIN,           // 프로젝트 입장 요청
    USER_JOINED_PROJECT,    // 프로젝트 입장 브로드캐스트

    PROJECT_LEFT,      // 프로젝트 퇴장 요청
    USER_LEFT_PROJECT,   // 프로젝트 퇴장 브로드캐스트

    PROJECT_RENAME,         // 프로젝트 이름 수정 요청
    PROJECT_RENAMED,        // 프로젝트 이름 수정 브로드캐스트

    PROJECT_TIME_SIGNATURE,             // 프로젝트 박자 수정 요청
    MODIFIED_PROJECT_TIME_SIGNATURE,    // 프로젝트 박자 수정 브로드캐스트

    PROJECT_KEY,            // 프로젝트 조성 수정 요청
    MODIFIED_PROJECT_KEY,   // 프로젝트 조성 수정 브로드캐스트

    PROJECT_BPM,            // 프로젝트 빠르기 수정 요청
    MODIFIED_PROJECT_BPM,   // 프로젝트 빠르기 수정 브로드캐스트
    ;

    public static ProjectWebSocketEventType from(String event) {
        for (ProjectWebSocketEventType value : values()) {
            if (value.name().equals(event)) {
                return value;
            }
        }
        return null;
    }
}
