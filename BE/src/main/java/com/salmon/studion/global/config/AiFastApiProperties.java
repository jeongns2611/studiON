package com.salmon.studion.global.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/*
    - 설정 파일 값을 자바 객체로 받는 역할
    - application.yaml의 ai.fastapi.* 값을 타입을 묶어주겠다.

    - Spring이 자동으로 케밥 케이스를 카멜 케이스로 바꿔줌
        - base-url => baseUrl 바인딩
        - timeout-seconds => timeoutSeconds 바인딩

    - record 사용 이유
        - AI에게 요청하는 객체는 읽기 전용이기 때문이다.
 */
@ConfigurationProperties(prefix = "ai.fastapi")
public record AiFastApiProperties (
    String baseUrl,
    long timeoutSeconds
){

}
