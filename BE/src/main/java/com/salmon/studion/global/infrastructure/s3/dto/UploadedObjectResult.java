package com.salmon.studion.global.infrastructure.s3.dto;

import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Getter;

@Getter
@AllArgsConstructor(access = AccessLevel.PRIVATE)
public class UploadedObjectResult {

    private String objectKey;
    private String storedName;
    private Long sizeBytes;

    public static UploadedObjectResult of(String objectKey, String storedName, Long sizeBytes) {
        return new UploadedObjectResult(objectKey, storedName, sizeBytes);
    }
}
