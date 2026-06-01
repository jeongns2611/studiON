package com.salmon.studion.global.common.enums;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum ProjectMode {
    MINOR("Minor"),
    MAJOR("Major");

    private final String value;

    @JsonCreator
    public static ProjectMode from(String value) {
        for (ProjectMode mode : ProjectMode.values()) {
            if (mode.value.equalsIgnoreCase(value) || mode.name().equalsIgnoreCase(value)) {
                return mode;
            }
        }
        // TODO: ErrorCode로 뺄지 고민중
        throw new IllegalArgumentException("지원하지 않는 mode 값입니다: " + value);
    }

    @JsonValue
    public String getValue() {
        return value;
    }
}
