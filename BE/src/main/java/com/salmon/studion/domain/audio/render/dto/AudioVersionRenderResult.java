package com.salmon.studion.domain.audio.render.dto;

import com.salmon.studion.global.common.enums.MimeType;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.nio.file.Path;

@Getter
@AllArgsConstructor(access = AccessLevel.PRIVATE)
public class AudioVersionRenderResult {

    private Path outputPath;
    private MimeType mimeType;
    private String originalName;
    private Integer durationMs;

    public static AudioVersionRenderResult of(Path outputPath, MimeType mimeType, String originalName, Integer durationMs) {
        return new AudioVersionRenderResult(outputPath, mimeType, originalName, durationMs);
    }
}
