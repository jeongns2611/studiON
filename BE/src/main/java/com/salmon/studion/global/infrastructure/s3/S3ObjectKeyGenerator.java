package com.salmon.studion.global.infrastructure.s3;

import org.springframework.stereotype.Component;

import com.salmon.studion.global.common.response.ErrorCode;
import com.salmon.studion.global.exception.BusinessException;

import java.util.UUID;

@Component
public class S3ObjectKeyGenerator {
    private static final String AUDIO_OBJECT_KEY_PREFIX = "projects/%d/audios/%s";
    private static final String MASTER_AUDIO_OBJECT_KEY_FORMAT = "projects/%d/master-audios/%s";

    public String createStoredName(String originalName) {
        String extension = extractExtension(originalName);
        return UUID.randomUUID() + "." + extension;
    }

    public String createAudioObjectKey(Integer projectId, String storedName) {
        return String.format(AUDIO_OBJECT_KEY_PREFIX, projectId, storedName);
    }

    public String createMasterAudioObjectKey(Integer projectId, String storedName) {
        return String.format(MASTER_AUDIO_OBJECT_KEY_FORMAT, projectId, storedName);
    }

    private String extractExtension(String originalName) {
        int dotIndex = originalName.lastIndexOf(".");

        if (dotIndex == -1 || dotIndex == originalName.length() - 1) {
            throw new BusinessException(ErrorCode.AUDIO_INVALID_FILE_NAME);
        }

        return originalName.substring(dotIndex + 1).toLowerCase();
    }
}
