package com.salmon.studion.global.common.enums;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

import java.util.Set;

@Getter
@RequiredArgsConstructor
public enum MimeType {
    MPEG("audio/mpeg"),
    WAV("audio/wav");

    private final String value;

    public boolean matchesExtension(String extension) {
        return switch (this) {
            case MPEG -> Set.of("mp3").contains(extension);
            case WAV -> Set.of("wav").contains(extension);
        };
    }
}
