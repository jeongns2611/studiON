package com.salmon.studion.domain.audio.dto.response;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.List;

@Getter
@NoArgsConstructor
@AllArgsConstructor
public class AudioVersionListResponse {

    private int totalVersion;
    private List<AudioVersionSummary> versions;

    public record AudioVersionSummary(
            Integer versionId,
            String name,
            String memo,
            Integer durationMs,
            Integer sizeBytes,
            Instant createdAt
    ) {
    }
}
