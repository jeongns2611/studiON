package com.salmon.studion.domain.audio.dto.response;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
@AllArgsConstructor
public class AudioVersionUploadUrlResponse {
    private String objectKey;
    private String storedName;
    private String uploadUrl;
}
