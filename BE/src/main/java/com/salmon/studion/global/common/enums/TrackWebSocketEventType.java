package com.salmon.studion.global.common.enums;

public enum TrackWebSocketEventType {
    TRACK_ADD,
    TRACK_DELETE,
    TRACK_REORDER,
    TRACK_RENAME,
    TRACK_SOLO_CHANGE,
    TRACK_MUTE_CHANGE,
    TRACK_VOLUME_CHANGE,
    TRACK_PAN_CHANGE
    ;

    public static TrackWebSocketEventType from(String event) {
        for (TrackWebSocketEventType value : values()) {
            if (value.name().equals(event)) {
                return value;
            }
        }
        return null;
    }
}
