package com.salmon.studion.global.common.enums;

public enum ClipWebSocketEventType {
    CLIP_LOCK,
    CLIP_MOVE,
    CLIP_RESIZE,
    CLIP_SPLIT,
    CLIP_DUPLICATE,
    CLIP_CUT,
    CLIP_COPY,
    CLIP_PASTE,
    CLIP_DELETE
    ;

    public static ClipWebSocketEventType from(String event) {
        for (ClipWebSocketEventType value : values()) {
            if (value.name().equals(event)) {
                return value;
            }
        }
        return null;
    }
}
