package com.salmon.studion.global.common.enums;

public enum CommentWebSocketEventType {

    COMMENT_ADD,        // 코멘트 등록 요청
    COMMENT_ADDED,      // 코멘트 등록 브로드캐스트

    COMMENT_DELETE,     // 코멘트 삭제 요청
    COMMENT_DELETED,    // 코멘트 삭제 브로드캐스트

    COMMENT_STATUS_CHANGE,   // 코멘트 해결 여부 변경 요청
    COMMENT_STATUS_CHANGED,  // 코멘트 해결 여부 변경 브로드캐스트
    ;

    public static CommentWebSocketEventType from(String event) {
        for (CommentWebSocketEventType value : values()) {
            if (value.name().equals(event)) {
                return value;
            }
        }
        return null;
    }
}
