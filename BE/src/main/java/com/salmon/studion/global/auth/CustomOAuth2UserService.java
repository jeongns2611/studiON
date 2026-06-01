package com.salmon.studion.global.auth;

import com.salmon.studion.domain.auth.entity.User;
import com.salmon.studion.domain.auth.repository.UserRepository;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.security.oauth2.client.userinfo.DefaultOAuth2UserService;
import org.springframework.security.oauth2.client.userinfo.OAuth2UserRequest;
import org.springframework.security.oauth2.client.userinfo.OAuth2UserService;
import org.springframework.security.oauth2.core.user.OAuth2User;
import org.springframework.stereotype.Service;

import java.time.Clock;
import java.util.Optional;

@Service
@RequiredArgsConstructor
public class CustomOAuth2UserService implements OAuth2UserService<OAuth2UserRequest, OAuth2User> {

    private final UserRepository userRepository;
    private final Clock clock;

    @Override
    @Transactional
    public OAuth2User loadUser(OAuth2UserRequest userRequest) {  // userRequest: 구글 사용자 정보 가져오는데 필요한 요청 정보 묶음
        OAuth2User oAuth2User = new DefaultOAuth2UserService().loadUser(userRequest);

        System.out.println("Google attributes = " + oAuth2User.getAttributes());

        String provider = userRequest.getClientRegistration().getRegistrationId();  // google
        String providerId = oAuth2User.getAttribute("sub");  // 사용자 식별 id
        String email = oAuth2User.getAttribute("email");  // 이메일
        String profileImgUrl = oAuth2User.getAttribute("picture");  // 프로필 사진
        String nickname = oAuth2User.getAttribute("name");  // 닉네임

        // 기존 회원인지 DB에서 조회
        Optional<User> optionalUser = userRepository.findByProviderAndProviderId(provider, providerId);

        if(optionalUser.isPresent()) {
            User existingUser = optionalUser.get();
            existingUser.updateLastLoginAt(clock.instant());
            return CustomOAuth2User.existingUser(existingUser, oAuth2User.getAttributes());
        }

        PendingOAuthUserInfo pendingOAuthUserInfo = new PendingOAuthUserInfo(
                email,
                provider,
                providerId,
                profileImgUrl,
                nickname
        );
        return CustomOAuth2User.newUser(pendingOAuthUserInfo, oAuth2User.getAttributes());
    }
}
