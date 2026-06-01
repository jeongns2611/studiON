package com.salmon.studion.domain.project.support;

import org.springframework.stereotype.Component;

import java.security.SecureRandom;

@Component
public class ProjectInviteCodeGenerator {

    private static final String BASE62 = "23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz";
    private static final int CODE_LENGTH = 8;

    private final SecureRandom secureRandom = new SecureRandom();

    public String generate() {
        StringBuilder code = new StringBuilder(CODE_LENGTH);

        for (int i = 0; i < CODE_LENGTH; i++) {
            int index = secureRandom.nextInt(BASE62.length());
            code.append(BASE62.charAt(index));
        }

        return code.toString();
    }
}
