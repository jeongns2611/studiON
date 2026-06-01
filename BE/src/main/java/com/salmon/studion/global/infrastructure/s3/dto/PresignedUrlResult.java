package com.salmon.studion.global.infrastructure.s3.dto;

import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor(access = AccessLevel.PRIVATE)
public class PresignedUrlResult {

    private String objectKey;
    private String storedName;
    private String uploadUrl;

    public static PresignedUrlResult of(
            String objectKey,
            String storedName,
            String uploadUrl
    ) {
        return new PresignedUrlResult(objectKey, storedName, uploadUrl);
    }
}