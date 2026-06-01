package com.salmon.studion.global.common.response;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Getter;

@Getter
@JsonInclude(JsonInclude.Include.NON_NULL)
public class ApiResponse<T> {

    private final Boolean isSuccess;
    private final String code;
    private final String message;
    private final T data;

    private ApiResponse(Boolean isSuccess, String code, String message, T data) {
        this.isSuccess = isSuccess;
        this.code = code;
        this.message = message;
        this.data = data;
    }

    // 성공: 기본 응답
    public static ApiResponse<Void> success() {
        return new ApiResponse<>(
                true,
                SuccessCode.SUCCESS.getCode(),
                SuccessCode.SUCCESS.getMessage(),
                null
        );
    }

    // 성공: 데이터만
    public static <T> ApiResponse<T> success(T data) {
        return new ApiResponse<>(
                true,
                SuccessCode.SUCCESS.getCode(),
                SuccessCode.SUCCESS.getMessage(),
                data
        );
    }

    // 성공: 코드+메시지
    public static ApiResponse<Void> success(SuccessCode successCode) {
        return new ApiResponse<>(
                true,
                successCode.getCode(),
                successCode.getMessage(),
                null
        );
    }

    // 성공: 코드+메시지+데이터
    public static <T> ApiResponse<T> success(SuccessCode successCode, T data) {
        return new ApiResponse<>(
                true,
                successCode.getCode(),
                successCode.getMessage(),
                data
        );
    }

    // 실패: 기본 응답
    public static ApiResponse<Void> fail() {
        return new ApiResponse<>(
                false,
                ErrorCode.FAIL.getCode(),
                ErrorCode.FAIL.getMessage(),
                null
        );
    }

    // 실패: 코드+메시지
    public static ApiResponse<Void> fail(ErrorCode errorCode) {
        return new ApiResponse<>(
                false,
                errorCode.getCode(),
                errorCode.getMessage(),
                null
        );
    }

    // 실패: 커스텀 메시지
    public static ApiResponse<Void> fail(ErrorCode errorCode, String message) {
        return new ApiResponse<>(
                false,
                errorCode.getCode(),
                message,
                null
        );
    }

    // 실패: 코드+메시지+데이터
    public static <T> ApiResponse<T> fail(ErrorCode errorCode, T data) {
        return new ApiResponse<>(
                false,
                errorCode.getCode(),
                errorCode.getMessage(),
                data
        );
    }

    // 완전 커스텀 응답
    public static <T> ApiResponse<T> of(Boolean isSuccess, String code, String message, T data) {
        return new ApiResponse<>(isSuccess, code, message, data);
    }

}
