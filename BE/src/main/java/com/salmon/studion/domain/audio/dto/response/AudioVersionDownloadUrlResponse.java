package com.salmon.studion.domain.audio.dto.response;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.Instant;

@Getter
@NoArgsConstructor
@AllArgsConstructor
public class AudioVersionDownloadUrlResponse {
    private Integer versionId;
    private String downloadUrl;
    private Instant expiresAt;

}
