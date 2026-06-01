package com.salmon.studion.domain.audio.dto.response;

import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor(access = AccessLevel.PRIVATE)
public class AudioUploadUrlResponse {

    private String objectKey;
    private String storedName;
    private String uploadUrl;

    public static AudioUploadUrlResponse of(String objectKey, String storedName, String uploadUrl) {
        return new AudioUploadUrlResponse(objectKey, storedName, uploadUrl);
    }
}
