package com.salmon.studion.global.config;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Configuration
@EnableConfigurationProperties(AudioUploadLimitProperties.class)
public class AudioUploadLimitConfig {
}
