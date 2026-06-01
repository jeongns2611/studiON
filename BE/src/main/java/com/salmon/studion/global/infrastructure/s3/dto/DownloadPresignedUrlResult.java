package com.salmon.studion.global.infrastructure.s3.dto;

import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Getter;

import java.time.Instant;

@Getter
@AllArgsConstructor(access = AccessLevel.PRIVATE)
public class DownloadPresignedUrlResult {

    private String downloadUrl;
    private Instant expiresAt;

    public static DownloadPresignedUrlResult of(String downloadUrl, Instant expiresAt) {
        return new DownloadPresignedUrlResult(downloadUrl, expiresAt);
    }
}
