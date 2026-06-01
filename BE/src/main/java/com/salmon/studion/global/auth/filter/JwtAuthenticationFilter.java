package com.salmon.studion.global.auth.filter;

import com.salmon.studion.domain.auth.entity.User;
import com.salmon.studion.domain.auth.repository.UserRepository;
import com.salmon.studion.global.auth.CustomOAuth2User;
import com.salmon.studion.global.auth.JwtTokenProvider;
import io.jsonwebtoken.JwtException;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.List;
import java.util.Map;

@Component
@RequiredArgsConstructor
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private static final String TOKEN_TYPE_ACCESS = "ACCESS";

    private final JwtTokenProvider jwtTokenProvider;
    private final UserRepository userRepository;

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {

        String header = request.getHeader("Authorization");

        if(header == null || !header.startsWith("Bearer ")) {
            filterChain.doFilter(request, response);
            return;
        }

        // "Bearer " 이후의 실제 JWT 문자열만 잘라냄
        String token = header.substring(7);  // "Bearer " 이후

        try {
            String tokenType = jwtTokenProvider.getTokenType(token);

            // 해당 토큰이 ACCESS 토큰이 아닌 경우
            if (!TOKEN_TYPE_ACCESS.equals(tokenType)) {
                response.sendError(HttpServletResponse.SC_UNAUTHORIZED, "ACCESS 토큰만 사용 가능합니다.");
                return;
            }

            Integer userId = jwtTokenProvider.getUserIdFromToken(token);

            User user = userRepository.findById(userId).orElse(null);
            if(user == null) {
                response.sendError(HttpServletResponse.SC_UNAUTHORIZED, "사용자를 찾을 수 없습니다.");
                return;
            }

            CustomOAuth2User principal = CustomOAuth2User.existingUser(user, Map.of());

            UsernamePasswordAuthenticationToken authentication =
                    new UsernamePasswordAuthenticationToken(principal, null, List.of());

            SecurityContextHolder.getContext().setAuthentication(authentication);

            // 여기까지 왔으면 유효한 ACCESS 토큰으로 인증 객체가 등록된 상태

        } catch (JwtException e) {
            response.sendError(HttpServletResponse.SC_UNAUTHORIZED, "유효하지 않은 토큰입니다.");
            return;
        } catch (IllegalArgumentException e) {
            response.sendError(HttpServletResponse.SC_UNAUTHORIZED, "잘못된 토큰 타입입니다.");
        }

        filterChain.doFilter(request, response);
    }
}
