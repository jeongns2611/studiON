package com.salmon.studion.domain.audio.service;

import com.salmon.studion.global.common.enums.UserRole;
import com.salmon.studion.global.config.AudioUploadLimitProperties;
import org.springframework.stereotype.Service;

@Service
public class AudioUploadLimitService {

    private final AudioUploadLimitProperties properties;

    public AudioUploadLimitService(AudioUploadLimitProperties properties) {
        this.properties = properties;
    }

    public AudioUploadLimit getLimit(UserRole role) {
        AudioUploadLimitProperties.Limit configuredLimit = role == UserRole.ADMIN
                ? properties.admin()
                : properties.basic();

        return new AudioUploadLimit(
                configuredLimit.maxFileSizeBytes(),
                configuredLimit.maxTotalSizeBytes()
        );
    }

    public record AudioUploadLimit(
            Integer maxFileSizeBytes,
            Long maxTotalSizeBytes
    ) {
    }
}
