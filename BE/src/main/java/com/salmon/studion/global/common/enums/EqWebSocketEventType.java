package com.salmon.studion.global.common.enums;

public enum EqWebSocketEventType {

    EQ_LOCK,
    EQ_DRAFT_SAVE,
    EQ_RESET,
    EQ_COMMIT;

    public static EqWebSocketEventType from(String event) {
        for (EqWebSocketEventType value : values()) {
            if (value.name().equals(event)) {
                return value;
            }
        }
        return null;
    }
}
