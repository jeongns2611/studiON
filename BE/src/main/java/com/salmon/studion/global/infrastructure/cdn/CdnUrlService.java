package com.salmon.studion.global.infrastructure.cdn;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
public class CdnUrlService {

    @Value("${cdn.domain}")
    private String cdnDomain;

    public String createAudioUrl(String objectKey) {
        return removeTrailingSlash(cdnDomain) + "/" + removeLeadingSlash(objectKey);
    }

    private String removeTrailingSlash(String value) {
        if (value.endsWith("/")) {
            return value.substring(0, value.length() - 1);
        }
        return value;
    }

    private String removeLeadingSlash(String value) {
        if (value.startsWith("/")) {
            return value.substring(1);
        }
        return value;
    }
}
