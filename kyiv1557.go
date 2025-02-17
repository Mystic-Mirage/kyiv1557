package main

import (
	"fmt"
	"io"
	"net/http"
	"net/http/cookiejar"
	"net/url"
	"strings"

	"github.com/PuerkitoBio/goquery"
	"gopkg.in/ini.v1"
)

const (
	mainUrl   = "https://1557.kyiv.ua/"
	loginPath = "login"

	selectId      = "address-select"
	msgBlockClass = "claim-message-block"
	msgItemClass  = "claim-message-item"
	msgWarnClass  = "claim-message-green"

	defaultConfigFilename = "1557.ini"
	configSection         = "1557"

	loginField = "phone"
	passField  = "pass"

	addrSwitchField = "main-address"

	msgDelimiter  = "---"
	addrDelimiter = "==="
)

type Kyiv1557Address struct {
	Id   string
	Name string
}

type Kyiv1557Message struct {
	Text string
	Warn bool
}

type Kyiv1557 struct {
	client *http.Client

	Addresses      []*Kyiv1557Address
	CurrentAddress *Kyiv1557Address
	Messages       []*Kyiv1557Message
}

func getUrl(paths ...string) string {
	return mainUrl + strings.Join(paths, "/")
}

func (k *Kyiv1557) parse(body io.ReadCloser) {
	defer body.Close()

	k.Addresses = nil
	k.CurrentAddress = nil
	k.Messages = nil

	doc, err := goquery.NewDocumentFromReader(body)
	if err != nil {
		return
	}

	doc.Find("select#" + selectId).Find("option").Each(
		func(i int, s *goquery.Selection) {
			id, _ := s.Attr("value")
			name := strings.TrimSpace(s.Text())

			address := &Kyiv1557Address{id, name}
			k.Addresses = append(k.Addresses, address)

			if _, exists := s.Attr("selected"); exists {
				k.CurrentAddress = address
			}

			if k.CurrentAddress == nil && len(k.Addresses) > 0 {
				k.CurrentAddress = k.Addresses[0]
			}
		},
	)

	doc.Find("div." + msgBlockClass).Each(
		func(i int, s *goquery.Selection) {
			paragraphs := []string{}

			s.Find("div." + msgItemClass).Each(
				func(i int, s *goquery.Selection) {
					lines := []string{}

					for _, line := range strings.Split(s.Text(), "\n") {
						line = strings.TrimSpace(line)
						lines = append(lines, line)
					}

					paragraph := strings.Join(lines, " ")
					paragraphs = append(paragraphs, paragraph)
				},
			)

			text := strings.Join(paragraphs, "\n")
			warn := s.HasClass(msgWarnClass)

			message := &Kyiv1557Message{text, warn}
			k.Messages = append(k.Messages, message)
		},
	)
}

func (k *Kyiv1557) Login(phone string, password string) {
	jar, err := cookiejar.New(nil)
	if err != nil {
		panic(err)
	}

	k.client = &http.Client{
		Jar: jar,
	}

	loginUrl := getUrl(loginPath)

	resp, err := k.client.PostForm(loginUrl, url.Values{loginField: {phone}})
	if err != nil {
		panic(err)
	}
	defer resp.Body.Close()

	redirectUrl := resp.Request.URL.String()
	resp, err = k.client.PostForm(redirectUrl, url.Values{passField: {password}})
	if err != nil {
		panic(err)
	}

	k.parse(resp.Body)
}

func (k *Kyiv1557) LoginFromFile(filename string) {
	if filename == "" {
		filename = defaultConfigFilename
	}

	cfg, err := ini.Load(filename)
	if err != nil {
		panic(err)
	}

	section := cfg.Section(configSection)

	phone := section.Key(loginField).String()
	password := section.Key(passField).String()

	k.Login(phone, password)
}

func (k *Kyiv1557) SelectAddress(address *Kyiv1557Address) {
	mainUrl := getUrl()

	resp, err := k.client.PostForm(mainUrl, url.Values{addrSwitchField: {address.Id}})
	if err != nil {
		panic(err)
	}

	k.parse(resp.Body)
}

func main() {
	kyiv1557 := Kyiv1557{}
	kyiv1557.LoginFromFile("")

	fmt.Println(kyiv1557.CurrentAddress.Name)
	for _, message := range kyiv1557.Messages {
		fmt.Println(msgDelimiter)
		fmt.Println(message.Text)
	}

	for _, address := range kyiv1557.Addresses[1:] {
		fmt.Println(addrDelimiter)
		kyiv1557.SelectAddress(address)

		fmt.Println(kyiv1557.CurrentAddress.Name)
		for _, message := range kyiv1557.Messages {
			fmt.Println(msgDelimiter)
			fmt.Println(message.Text)
		}
	}

}
