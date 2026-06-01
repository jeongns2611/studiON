package com.salmon.studion.domain.audio.dto.response;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
@AllArgsConstructor
public class AudioVersionDeleteResponse {
    private Integer versionId;
    private Boolean deleted;
}
