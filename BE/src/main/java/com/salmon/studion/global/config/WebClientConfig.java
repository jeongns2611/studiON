package com.salmon.studion.global.config;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.function.client.ExchangeStrategies;
import org.springframework.web.reactive.function.client.WebClient;

/*
    - Spring 설정 클래스
    - @Configuration
        - 이 클래스 안에 빈 등록 메서드가 있다.는 뜻
    - @EnableConfigurationProperties(AiFastApiProperties.class)
        - AIFastApiProperties를 스프링 빈으로 등록하여 다른 곳에서 주입받을 수 있게 만듬
        - 이 어노테이션을 통해 AiFastApiProperties properties를 받아올 수 있음
        
    - 성과
        - URL 하드코딩을 막음
        - 테스트할 때 설정값만 바꿔서 다른 서버를 보게 할 수 있음
        - 외부 API 호출 설정을 이곳에서만 하면 됨
 */
@Configuration
@EnableConfigurationProperties(AiFastApiProperties.class)
public class WebClientConfig {

    // WebClient 객체를 만들어 스프링 컨테이너가 관리하게 함
    @Bean
    public WebClient aiWebClient(WebClient.Builder builder, AiFastApiProperties properties) {

        ExchangeStrategies strategies = ExchangeStrategies.builder()
              .codecs(configurer -> configurer.defaultCodecs().maxInMemorySize(2 * 1024 * 1024))
              .build();

        return builder
                .baseUrl(properties.baseUrl())      // base-url로 baseUrl을 지정
                .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)      // 기본 요청 헤더 주입, Content-Type: application/json
                .exchangeStrategies(strategies)
                .build();
    }
}
