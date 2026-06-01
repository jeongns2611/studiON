package com.salmon.studion.global.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "app.audio.upload-limit")
public record AudioUploadLimitProperties(
        Limit basic,
        Limit admin
) {

    public record Limit(
            Integer maxFileSizeBytes,
            Long maxTotalSizeBytes
    ) {
    }
}
