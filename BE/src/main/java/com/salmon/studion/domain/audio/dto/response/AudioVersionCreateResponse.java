package com.salmon.studion.domain.audio.dto.response;

import com.salmon.studion.global.common.enums.AudioVersionStatus;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.Instant;

@Getter
@NoArgsConstructor
@AllArgsConstructor
public class AudioVersionCreateResponse {
    private Integer versionId;
    private String name;
    private AudioVersionStatus status;
    private Instant createdAt;
}
