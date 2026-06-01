package com.salmon.studion.global.config;

import com.salmon.studion.global.auth.CustomOAuth2User;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.domain.AuditorAware;
import org.springframework.data.jpa.repository.config.EnableJpaAuditing;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

import java.util.Optional;

@Configuration
@EnableJpaAuditing
public class JpaAuditingConfig {

    @Bean
    public AuditorAware<Integer> auditorProvider() {
        return () -> {
            Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
            if(authentication == null || !authentication.isAuthenticated()) {
                return Optional.of(0);
            }
            Object principal = authentication.getPrincipal();
            if(principal instanceof CustomOAuth2User customOAuth2User) {
                return Optional.of(customOAuth2User.getUserId());
            }
            return Optional.ofNullable(authentication.getName())
                    .filter(name -> name.chars().allMatch(Character::isDigit))
                    .map(Integer::valueOf)
                    .or(() -> Optional.of(0));
        };
    }
}
