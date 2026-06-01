package com.salmon.studion.global.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class SwaggerConfig {
    @Bean
    public OpenAPI openAPI() {
        return new OpenAPI()
                .info(apiInfo());
    }

    private Info apiInfo() {
        return new Info()
                .title("Studion API")
                .description("""
                        Studion API 명세서입니다.
                        
                        ### 관련 링크
                        - [GitLab Repo](https://lab.ssafy.com/s14-final/S14P31A205)
                        - [Jira](https://ssafy.atlassian.net/jira/software/c/projects/S14P31A205/boards/13109)
                        - [Figma](https://www.figma.com/design/DyvCe8iflRktfSklgHiLim/StudiON?node-id=354-3919&t=EQAl1ZzfifCFXFAm-0)
                        - [서비스 배포 주소](https://studion.ai.kr/)
                        """)
                .version("v1.0.0")
                ;
    }
}
